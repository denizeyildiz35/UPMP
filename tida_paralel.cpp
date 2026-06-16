// Python'dan C++ kütüphanesi olarak çağırabilmek için pybind11 ana başlığı
#include <pybind11/pybind11.h>
// Python listelerini C++ vektörlerine otomatik dönüştüren pybind11 eklentisi
#include <pybind11/stl.h>

#include <iostream>
#include <vector>
#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <unordered_map>
#include <chrono>
#include <random>
#include <limits>
#include <algorithm>
// Paralel IDA* için atomik paylaşılan durum
#include <atomic>
// Tek merkezi iş kuyruğu
#include <deque>
// Kuyruğu ve çözüm yolunu korumak için
#include <mutex>
// Worker thread'leri
#include <thread>

namespace py = pybind11;

constexpr int MAX_LANES    = 100;
constexpr int MAX_LEN      = 20;
constexpr int MAX_DATA     = MAX_LANES * MAX_LEN;
constexpr int MAX_PRIORITY = 6;

// DFS dönüş sinyalleri
constexpr double IDA_FOUND = -1.0;
constexpr double IDA_STOP  = -2.0;

// ── Veri yapıları ─────────────────────────────────────────────────────────

struct Layout {
    int num_lanes;
    int max_len;
    std::array<int, MAX_LANES> lane_lens;
};

struct State {
    std::array<uint8_t, MAX_DATA> data{};
    inline uint8_t& at(const Layout& L, int lane, int slot)       { return data[lane * L.max_len + slot]; }
    inline uint8_t  at(const Layout& L, int lane, int slot) const { return data[lane * L.max_len + slot]; }
};

struct ZobristTable {
    std::array<std::array<uint64_t, 256>, MAX_DATA> table;
    ZobristTable() {
        std::mt19937_64 rng(0xDEADBEEF);
        for (int i = 0; i < MAX_DATA; i++)
            for (int j = 0; j < 256; j++)
                table[i][j] = rng();
    }
    uint64_t full_hash(const State& s, const Layout& L) const {
        uint64_t h = 0;
        for (int i = 0; i < L.num_lanes * L.max_len; i++)
            h ^= table[i][s.data[i]];
        return h;
    }
};

static const ZobristTable g_zobrist;

struct IdentityHash {
    size_t operator()(uint64_t x) const noexcept { return x; }
};

struct LaneLBInfo {
    std::array<int, MAX_PRIORITY> demand_contrib{};
    int  supply_key   = 0;
    int  supply_count = 0;
    int  k_param      = 0;
    int  p_param      = 0;
    int  orig_len     = 0;
    bool has_small    = false;
    int  empty_slots  = 0;
};

struct Node {
    State    state;
    uint64_t hash;
    int      g;
    double   h;
    double   f;

    std::array<uint8_t, MAX_LANES>    lane_blocking{};
    int                               total_blocking = 0;
    int                               n_h            = 0;

    std::array<LaneLBInfo, MAX_LANES> lane_lb{};
    std::array<int, MAX_PRIORITY>     total_demand{};
    std::array<int, MAX_PRIORITY>     total_supply{};
    int                               total_empty_slots = 0;

    int    g_star     = -1;
    int    ds_gstar   = 0;
    double extra_cost = 0.0;

    int src_lane = -1;
    int dst_lane = -1;
};

struct MoveRecord {
    int    src_lane;
    int    src_slot;
    int    dst_lane;
    int    dst_slot;
    int    item;
    int    g;
    double h;
    double f;
    double time_sec;
};

// ── Yardımcı fonksiyonlar (tek-thread versiyonla aynı) ──────────────────────

std::pair<Layout, State> from_python(const std::vector<std::vector<int>>& lanes) {
    Layout L;
    L.num_lanes = (int)lanes.size();
    L.max_len   = 0;
    for (const auto& lane : lanes)
        if ((int)lane.size() > L.max_len) L.max_len = (int)lane.size();
    for (int i = 0; i < L.num_lanes; ++i)
        L.lane_lens[i] = (int)lanes[i].size();
    State s;
    for (int li = 0; li < L.num_lanes; ++li)
        for (int slot = 0; slot < L.lane_lens[li]; ++slot)
            s.at(L, li, slot) = (uint8_t)lanes[li][slot];
    return { L, s };
}

inline uint8_t lane_blocking_calc(const State& s, const Layout& L, int li) {
    int lane_len = L.lane_lens[li];
    uint8_t prev = 0;
    for (int i = 0; i < lane_len; ++i) {
        uint8_t val = s.at(L, li, i);
        if (val == 0) continue;
        if (prev != 0 && val > prev) {
            int remaining = 0;
            for (int j = i; j < lane_len; ++j)
                if (s.at(L, li, j) != 0) remaining++;
            return (uint8_t)remaining;
        }
        prev = val;
    }
    return 0;
}

LaneLBInfo lane_lb_calc(const State& s, const Layout& L, int li, int g_star) {
    LaneLBInfo info;
    info.orig_len = L.lane_lens[li];
    int lane_len  = L.lane_lens[li];

    std::array<uint8_t, MAX_LEN> items{};
    int n = 0;
    for (int i = 0; i < lane_len; ++i) {
        uint8_t v = s.at(L, li, i);
        if (v != 0) items[n++] = v;
    }
    if (n == 0) {
        info.empty_slots = lane_len;
        return info;
    }

    for (int i = n - 1; i > 0; --i) {
        if (items[i - 1] > items[i]) {
            for (int j = 0; j < i; ++j) {
                int p = (int)items[j];
                if (p >= 1 && p < MAX_PRIORITY) info.demand_contrib[p]++;
            }
            break;
        }
    }

    int seg_end = lane_len - 1;
    while (seg_end >= 0 && s.at(L, li, seg_end) == 0) --seg_end;
    if (seg_end < 0) return info;

    int prev    = (int)s.at(L, li, seg_end);
    int seg_beg = seg_end - 1;
    while (seg_beg >= 0) {
        int cur = (int)s.at(L, li, seg_beg);
        if (cur == 0) { --seg_beg; continue; }
        if (cur > prev && prev != 0) break;
        prev = cur;
        --seg_beg;
    }

    if (seg_beg >= 0 && prev != 0 && prev < MAX_PRIORITY) {
        info.supply_key   = prev;
        info.supply_count = seg_beg + 1;
    }

    if (g_star > 0) {
        int k_param = 0, cnt_ge = 0;
        bool has_small = false;
        for (int idx = seg_beg + 1; idx <= seg_end; ++idx) {
            int v = (int)s.at(L, li, idx);
            if (v == 0) continue;
            if (v < g_star) { k_param++; has_small = true; }
            if (v >= g_star) { cnt_ge++; }
        }
        info.has_small = has_small;
        if (has_small) {
            info.k_param = k_param;
            info.p_param = info.orig_len - cnt_ge;
        }
    }
    return info;
}

void compute_all_lane_lb(const State& s, const Layout& L, Node& node, int g_star) {
    node.total_demand.fill(0);
    node.total_supply.fill(0);
    node.total_empty_slots = 0;
    for (int li = 0; li < L.num_lanes; ++li) {
        node.lane_lb[li] = lane_lb_calc(s, L, li, g_star);
        const LaneLBInfo& info = node.lane_lb[li];
        for (int p = 1; p < MAX_PRIORITY; ++p)
            node.total_demand[p] += info.demand_contrib[p];
        if (info.supply_key >= 1 && info.supply_key < MAX_PRIORITY)
            node.total_supply[info.supply_key] += info.supply_count;
        node.total_empty_slots += info.empty_slots;
    }
}

void compute_all_lane_blocking(const State& s, const Layout& L,
    std::array<uint8_t, MAX_LANES>& lb, int& total, int& n_h)
{
    total = 0;
    n_h   = 255;
    for (int li = 0; li < L.num_lanes; ++li) {
        lb[li]  = lane_blocking_calc(s, L, li);
        total  += lb[li];
        if ((int)lb[li] < n_h) n_h = (int)lb[li];
    }
    if (n_h == 255) n_h = 0;
}

std::pair<int, int> compute_g_star(
    const std::array<int, MAX_PRIORITY>& d,
    const std::array<int, MAX_PRIORITY>& s)
{
    int best_key = 1, best_val = std::numeric_limits<int>::min();
    int cum_d = 0, cum_s = 0;
    for (int p = MAX_PRIORITY - 1; p >= 1; --p) {
        cum_d += d[p]; cum_s += s[p];
        int surplus = cum_d - cum_s;
        if (surplus > best_val) { best_val = surplus; best_key = p; }
    }
    return { best_key, best_val };
}

double knapsack_dp(int B, const std::array<LaneLBInfo, MAX_LANES>& lane_lb, int num_lanes) {
    if (B <= 0) return 0.0;
    const int INF = 1000000000;
    std::vector<int> dp(B + 1, INF);
    dp[0] = 0;
    int p_sum = 0;
    for (int li = 0; li < num_lanes; ++li) {
        const LaneLBInfo& info = lane_lb[li];
        if (!info.has_small) continue;
        int p = info.p_param, c = info.k_param;
        if (p > 0) p_sum += p;
        if (p <= 0 && c >= 0) continue;
        if (p < 0) p = 0;
        for (int s2 = B; s2 >= 0; --s2) {
            if (dp[s2] >= INF) continue;
            int ns = std::min(s2 + p, B);
            int nv = dp[s2] + c;
            if (nv < dp[ns]) dp[ns] = nv;
        }
    }
    if (p_sum < B) return 0.0;
    return (dp[B] >= INF) ? 0.0 : (double)dp[B];
}

inline int find_pickable(const State& s, const Layout& L, int lane) {
    for (int i = 0; i < L.lane_lens[lane]; ++i)
        if (s.at(L, lane, i) != 0) return i;
    return -1;
}

inline int find_placeable(const State& s, const Layout& L, int lane) {
    for (int i = 0; i < L.lane_lens[lane]; ++i) {
        if (s.at(L, lane, i) != 0)
            return (i > 0) ? i - 1 : -1;
    }
    return L.lane_lens[lane] - 1;
}

constexpr int IDA_LOG_INTERVAL = 50000;

std::optional<Node> make_one_successor(const Node& parent, const Layout& L,
                                       int src_lane, int dst_lane)
{
    int pick_idx = find_pickable(parent.state, L, src_lane);
    if (pick_idx == -1) return std::nullopt;

    uint8_t item    = parent.state.at(L, src_lane, pick_idx);
    int     src_pos = src_lane * L.max_len + pick_idx;

    State new_state = parent.state;
    new_state.at(L, src_lane, pick_idx) = 0;

    int place_idx = find_placeable(new_state, L, dst_lane);
    if (place_idx == -1) return std::nullopt;

    int dst_pos = dst_lane * L.max_len + place_idx;
    new_state.at(L, dst_lane, place_idx) = item;

    uint64_t new_hash = parent.hash;
    new_hash ^= g_zobrist.table[src_pos][item];
    new_hash ^= g_zobrist.table[src_pos][0];
    new_hash ^= g_zobrist.table[dst_pos][0];
    new_hash ^= g_zobrist.table[dst_pos][item];

    uint8_t old_src_b = parent.lane_blocking[src_lane];
    uint8_t old_dst_b = parent.lane_blocking[dst_lane];
    uint8_t new_src_b = lane_blocking_calc(new_state, L, src_lane);
    uint8_t new_dst_b = lane_blocking_calc(new_state, L, dst_lane);

    int n_h;
    int new_src_i    = (int)new_src_b;
    int new_dst_i    = (int)new_dst_b;
    int new_min_cand = std::min(new_src_i, new_dst_i);
    if (new_min_cand <= parent.n_h) {
        n_h = std::min(parent.n_h, new_min_cand);
    } else if (((int)old_src_b == parent.n_h && new_src_i > parent.n_h) ||
               ((int)old_dst_b == parent.n_h && new_dst_i > parent.n_h)) {
        n_h = new_min_cand;
        for (int li = 0; li < L.num_lanes; ++li) {
            if (li == src_lane || li == dst_lane) continue;
            int v = (int)parent.lane_blocking[li];
            if (v < n_h) n_h = v;
        }
    } else {
        n_h = parent.n_h;
    }

    std::array<int, MAX_PRIORITY> new_td = parent.total_demand;
    std::array<int, MAX_PRIORITY> new_ts = parent.total_supply;
    int new_total_empty = parent.total_empty_slots;

    const LaneLBInfo& old_si = parent.lane_lb[src_lane];
    const LaneLBInfo& old_di = parent.lane_lb[dst_lane];

    for (int p = 1; p < MAX_PRIORITY; ++p) {
        new_td[p] -= old_si.demand_contrib[p];
        new_td[p] -= old_di.demand_contrib[p];
    }
    if (old_si.supply_key >= 1 && old_si.supply_key < MAX_PRIORITY)
        new_ts[old_si.supply_key] -= old_si.supply_count;
    if (old_di.supply_key >= 1 && old_di.supply_key < MAX_PRIORITY)
        new_ts[old_di.supply_key] -= old_di.supply_count;
    new_total_empty -= old_si.empty_slots;
    new_total_empty -= old_di.empty_slots;

    LaneLBInfo new_src_info = lane_lb_calc(new_state, L, src_lane, 0);
    LaneLBInfo new_dst_info = lane_lb_calc(new_state, L, dst_lane, 0);

    for (int p = 1; p < MAX_PRIORITY; ++p) {
        new_td[p] += new_src_info.demand_contrib[p];
        new_td[p] += new_dst_info.demand_contrib[p];
    }
    if (new_src_info.supply_key >= 1 && new_src_info.supply_key < MAX_PRIORITY)
        new_ts[new_src_info.supply_key] += new_src_info.supply_count;
    if (new_dst_info.supply_key >= 1 && new_dst_info.supply_key < MAX_PRIORITY)
        new_ts[new_dst_info.supply_key] += new_dst_info.supply_count;
    new_total_empty += new_src_info.empty_slots;
    new_total_empty += new_dst_info.empty_slots;

    int new_total_blocking = 0;
    for (int p = 1; p < MAX_PRIORITY; ++p)
        new_total_blocking += new_td[p];

    auto [new_g_star, new_ds_gstar] = compute_g_star(new_td, new_ts);
    new_ds_gstar -= new_total_empty;

    std::array<LaneLBInfo, MAX_LANES> new_lane_lb = parent.lane_lb;
    LaneLBInfo new_src_full = lane_lb_calc(new_state, L, src_lane, new_g_star);
    LaneLBInfo new_dst_full = lane_lb_calc(new_state, L, dst_lane, new_g_star);
    new_lane_lb[src_lane]   = new_src_full;
    new_lane_lb[dst_lane]   = new_dst_full;

    if (new_g_star != parent.g_star) {
        for (int li = 0; li < L.num_lanes; ++li) {
            if (li == src_lane || li == dst_lane) continue;
            new_lane_lb[li] = lane_lb_calc(new_state, L, li, new_g_star);
        }
    }

    double new_extra = 0.0;
    if (new_ds_gstar <= 0) {
        new_extra = 0.0;
    } else if (new_g_star    == parent.g_star    &&
               new_ds_gstar  == parent.ds_gstar  &&
               new_src_full.k_param   == old_si.k_param   &&
               new_src_full.p_param   == old_si.p_param   &&
               new_src_full.has_small == old_si.has_small &&
               new_dst_full.k_param   == old_di.k_param   &&
               new_dst_full.p_param   == old_di.p_param   &&
               new_dst_full.has_small == old_di.has_small) {
        new_extra = parent.extra_cost;
    } else {
        new_extra = knapsack_dp(new_ds_gstar, new_lane_lb, L.num_lanes);
    }

    Node succ;
    succ.state    = std::move(new_state);
    succ.hash     = new_hash;
    succ.g        = parent.g + 1;
    succ.src_lane = src_lane;
    succ.dst_lane = dst_lane;

    succ.lane_blocking           = parent.lane_blocking;
    succ.lane_blocking[src_lane] = new_src_b;
    succ.lane_blocking[dst_lane] = new_dst_b;
    succ.total_blocking          = new_total_blocking;
    succ.n_h                     = n_h;

    succ.lane_lb           = new_lane_lb;
    succ.total_demand      = new_td;
    succ.total_supply      = new_ts;
    succ.total_empty_slots = new_total_empty;
    succ.g_star            = new_g_star;
    succ.ds_gstar          = new_ds_gstar;
    succ.extra_cost        = new_extra;

    succ.h = (double)new_total_blocking + new_extra;
    succ.f = (double)succ.g + succ.h;
    return succ;
}

// ── DSG* tiebreak ──────────────────────────────────────────────────────────

// Sıralama için küçük aday struct'ı (tam Node ~7.5KB yerine ~36 byte)
struct CandMove {
    int     src_lane;
    int     dst_lane;
    double  f;
    double  h;
    int64_t dsg_score;
    int     g;
};

// Parent → child geçişindeki ağırlıklı demand-surplus değişimi.
// weight = 10^(p-1): yüksek öncelik üstel olarak daha ağır basar.
// int64_t: uzun aramalarda 32-bit taşar.
int64_t compute_dsg_delta(const Node& parent, const Node& child) {
    int64_t total = 0;
    int cum_pd = 0, cum_ps = 0;
    int cum_cd = 0, cum_cs = 0;
    for (int p = MAX_PRIORITY - 1; p >= 1; --p) {
        cum_pd += parent.total_demand[p];
        cum_ps += parent.total_supply[p];
        cum_cd += child.total_demand[p];
        cum_cs += child.total_supply[p];
        int diff = (cum_cd - cum_cs) - (cum_pd - cum_ps);
        if (diff != 0) {
            int64_t weight = 1;
            for (int i = 0; i < p - 1; ++i) weight *= 10;
            total += (int64_t)diff * weight;
        }
    }
    return total;
}

// Ebeveynin tüm geçerli haleflerini aday liste olarak üret.
// use_dsg açıksa her aday için dsg_score hesaplanır ve eşit-f durumunda
// daha iyi dsg_score'lu aday tercih edilir.
std::vector<CandMove> generate_candidates(const Node& parent, const Layout& L,
                                          int64_t parent_dsg_score, bool use_dsg)
{
    std::unordered_map<uint64_t, CandMove, IdentityHash> best_per_hash;
    best_per_hash.reserve(L.num_lanes * (L.num_lanes - 1));

    for (int src_lane = 0; src_lane < L.num_lanes; ++src_lane) {
        if (find_pickable(parent.state, L, src_lane) == -1) continue;
        for (int dst_lane = 0; dst_lane < L.num_lanes; ++dst_lane) {
            if (dst_lane == src_lane) continue;
            if (src_lane == parent.dst_lane && dst_lane == parent.src_lane) continue;

            auto opt = make_one_successor(parent, L, src_lane, dst_lane);
            if (!opt) continue;

            // DSG* skoru: h iyileştiyse skoru sıfırla, yoksa biriktir
            int64_t dsg_score = 0;
            if (use_dsg) {
                int64_t delta      = compute_dsg_delta(parent, *opt);
                bool    h_improved = opt->h < parent.h;
                dsg_score = h_improved ? delta : (parent_dsg_score + delta);
            }

            // Aynı hash için en iyi (f, dsg_score) tut, Node'u hemen serbest bırak
            auto it = best_per_hash.find(opt->hash);
            bool is_better = (it == best_per_hash.end()) ||
                             (opt->f < it->second.f) ||
                             (opt->f == it->second.f && dsg_score < it->second.dsg_score);
            if (is_better)
                best_per_hash[opt->hash] = CandMove{src_lane, dst_lane, opt->f,
                                                    opt->h, dsg_score, opt->g};
        }
    }

    std::vector<CandMove> result;
    result.reserve(best_per_hash.size());
    for (auto& kv : best_per_hash)
        result.push_back(kv.second);
    return result;
}

// Adayları seçilen moda göre sırala
void sort_candidates(std::vector<CandMove>& cands, bool use_dsg) {
    if (use_dsg) {
        std::sort(cands.begin(), cands.end(),
                  [](const CandMove& a, const CandMove& b) {
                      if (a.f != b.f)                 return a.f < b.f;
                      if (a.h != b.h)                 return a.h < b.h;
                      if (a.dsg_score != b.dsg_score) return a.dsg_score < b.dsg_score;
                      return a.g > b.g;
                  });
    } else {
        std::sort(cands.begin(), cands.end(),
                  [](const CandMove& a, const CandMove& b) { return a.f < b.f; });
    }
}

MoveRecord make_move_record(const Node& parent, const Node& child, const Layout& L)
{
    MoveRecord mr;
    int src_slot = find_pickable(parent.state, L, child.src_lane);
    int dst_slot = find_pickable(child.state,  L, child.dst_lane);
    int item_val = (dst_slot >= 0) ? (int)child.state.at(L, child.dst_lane, dst_slot) : 0;
    mr.src_lane = child.src_lane;  mr.src_slot = src_slot;
    mr.dst_lane = child.dst_lane;  mr.dst_slot = dst_slot;
    mr.item     = item_val;
    mr.g        = child.g;  mr.h = child.h;  mr.f = child.f;  mr.time_sec = 0.0;
    return mr;
}

// ── Paralel altyapı (sade) ──────────────────────────────────────────────────

// Bir worker'ın kendi sayaçları (thread-local, yarış yok)
struct ThreadStats {
    long long nodes_expanded = 0;
    long long last_log_at    = 0;
    double    min_h_seen     = std::numeric_limits<double>::infinity();
};

// Kuyruktaki tek iş birimi: kök çocuğu + ona kadarki yol öneki + başlangıç dsg skoru
struct WorkItem {
    Node                    node;
    std::vector<MoveRecord> path_prefix;
    int64_t                 init_dsg = 0;   // bu kök çocuğunun biriken DSG skoru
};

// Tek merkezi iş kuyruğu, kendi mutex'iyle
struct WorkQueue {
    std::deque<WorkItem> items;
    std::mutex           mutex;

    bool pop(WorkItem& out) {
        std::lock_guard<std::mutex> lock(mutex);
        if (items.empty()) return false;
        out = std::move(items.front());
        items.pop_front();
        return true;
    }
    void clear() {
        std::lock_guard<std::mutex> lock(mutex);
        items.clear();
    }
};

void atomic_min_double(std::atomic<double>& target, double value)
{
    double current = target.load(std::memory_order_relaxed);
    while (value < current &&
           !target.compare_exchange_weak(current, value,
                                         std::memory_order_relaxed,
                                         std::memory_order_relaxed)) {}
}

// Kök çocuklarını üret (her iterasyonda aynı, bir kez hesaplanıp kopyalanır).
// use_dsg açıksa her çocuğun başlangıç dsg skoru WorkItem'a yazılır.
std::deque<WorkItem> build_root_work_items(const Node& root, const Layout& L, bool use_dsg)
{
    // Kök için biriken skor 0
    std::vector<CandMove> cands = generate_candidates(root, L, 0, use_dsg);
    sort_candidates(cands, use_dsg);

    std::deque<WorkItem> items;
    for (const auto& cand : cands) {
        auto opt_child = make_one_successor(root, L, cand.src_lane, cand.dst_lane);
        if (!opt_child) continue;
        WorkItem item;
        item.node = std::move(*opt_child);
        item.path_prefix.push_back(make_move_record(root, item.node, L));
        item.init_dsg = cand.dsg_score;   // child'ın biriken skoru
        items.push_back(std::move(item));
    }
    return items;
}

// ── IDA* derinlik-öncelikli arama (DFS) ─────────────────────────────────────
// Her worker kendi call stack'iyle bağımsız çağırır.
// accumulated_dsg: bu düğüme kadar biriken DSG skoru (use_dsg açıkken anlamlı)
// Dönüş: IDA_FOUND | IDA_STOP | +inf (bu dal tükendi)
double dfs(
    const Node&                                    node,
    const Layout&                                  L,
    const std::atomic<double>&                     threshold,
    std::atomic<double>&                           min_exceeded,
    const std::atomic<bool>&                       found,
    std::atomic<bool>&                             stop_requested,
    int                                            iteration,
    std::vector<MoveRecord>&                       path,
    ThreadStats&                                   stats,
    int64_t                                        accumulated_dsg,
    bool                                           use_dsg,
    std::chrono::steady_clock::time_point          t_start,
    const std::function<void(const std::string&)>& log,
    const std::function<bool()>&                   check_stop)
{
    if (found.load(std::memory_order_acquire)) return std::numeric_limits<double>::infinity();
    if (stop_requested.load(std::memory_order_acquire)) return IDA_STOP;

    double f = (double)node.g + node.h;
    double threshold_value = threshold.load(std::memory_order_acquire);
    if (f > threshold_value) {
        atomic_min_double(min_exceeded, f);
        return f;
    }
    if (node.total_blocking == 0) return IDA_FOUND;

    stats.nodes_expanded++;
    if (node.h < stats.min_h_seen) stats.min_h_seen = node.h;

    if (stats.nodes_expanded % 1000 == 0 && check_stop()) {
        stop_requested.store(true, std::memory_order_release);
        return IDA_STOP;
    }

    if (stats.nodes_expanded - stats.last_log_at >= IDA_LOG_INTERVAL) {
        stats.last_log_at = stats.nodes_expanded;
        double elapsed = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - t_start).count();
        log("[IDA*] iter=" + std::to_string(iteration)
            + " | thread_nodes=" + std::to_string(stats.nodes_expanded)
            + " | esik=" + std::to_string(threshold_value)
            + " | min_h=" + std::to_string(stats.min_h_seen)
            + " | sure=" + std::to_string(elapsed) + "s\n");
    }

    std::vector<CandMove> cands = generate_candidates(node, L, accumulated_dsg, use_dsg);
    sort_candidates(cands, use_dsg);

    for (const auto& cand : cands) {
        if (found.load(std::memory_order_acquire)) return std::numeric_limits<double>::infinity();
        if (stop_requested.load(std::memory_order_acquire)) return IDA_STOP;

        auto opt_succ = make_one_successor(node, L, cand.src_lane, cand.dst_lane);
        if (!opt_succ) continue;
        Node s = std::move(*opt_succ);

        path.push_back(make_move_record(node, s, L));
        // Çocuğun biriken skoru cand.dsg_score; bir alt seviyeye onu taşı
        double result = dfs(s, L, threshold, min_exceeded, found, stop_requested,
                            iteration, path, stats, cand.dsg_score, use_dsg,
                            t_start, log, check_stop);
        if (result == IDA_FOUND) return IDA_FOUND;
        if (result == IDA_STOP)  return IDA_STOP;
        path.pop_back();
    }

    return std::numeric_limits<double>::infinity();
}

// ── Python'dan çağrılan ana fonksiyon (fork-join modeli) ────────────────────

py::object ida_star(const std::vector<std::vector<int>>& lanes,
                    py::object log_fn           = py::none(),
                    py::object stop_get_best_fn = py::none(),
                    py::object stop_fn          = py::none(),
                    bool       use_dsg_tiebreak = false,
                    int        num_threads      = 8)
{
    auto t_start = std::chrono::steady_clock::now();

    auto log = [&log_fn](const std::string& msg) noexcept {
        try {
            if (!log_fn.is_none()) {
                py::gil_scoped_acquire gil;
                log_fn(py::str(msg));
            } else {
                std::cout << msg;
            }
        } catch (...) {
            std::cerr << "Log callback hatasi.\n";
        }
    };

    auto check_stop = [&stop_fn]() noexcept -> bool {
        try {
            if (stop_fn.is_none()) return false;
            py::gil_scoped_acquire gil;
            return stop_fn().cast<bool>();
        } catch (...) {
            return true;
        }
    };

    auto check_stop_get_best = [&stop_get_best_fn]() noexcept -> bool {
        try {
            if (stop_get_best_fn.is_none()) return false;
            py::gil_scoped_acquire gil;
            return stop_get_best_fn().cast<bool>();
        } catch (...) {
            return true;
        }
    };

    auto [L, root_state] = from_python(lanes);

    // ── Kök düğümü kur ──────────────────────────────────────────────────────
    Node root;
    root.state    = root_state;
    root.hash     = g_zobrist.full_hash(root_state, L);
    root.g        = 0;
    root.src_lane = -1;
    root.dst_lane = -1;

    compute_all_lane_blocking(root_state, L, root.lane_blocking, root.total_blocking, root.n_h);
    compute_all_lane_lb(root_state, L, root, 0);
    auto [g_star, ds_gstar] = compute_g_star(root.total_demand, root.total_supply);
    ds_gstar -= root.total_empty_slots;
    root.g_star   = g_star;
    root.ds_gstar = ds_gstar;
    compute_all_lane_lb(root_state, L, root, g_star);
    root.extra_cost = knapsack_dp(ds_gstar, root.lane_lb, L.num_lanes);

    root.total_blocking = 0;
    for (int p = 1; p < MAX_PRIORITY; ++p)
        root.total_blocking += root.total_demand[p];

    root.h = (double)root.total_blocking + root.extra_cost;
    root.f = root.g + root.h;

    log("IDA* basladi. blokaj=" + std::to_string(root.total_blocking)
        + " g*=" + std::to_string(g_star)
        + " DS=" + std::to_string(ds_gstar)
        + " h=" + std::to_string(root.h)
        + " dsg_tiebreak=" + std::string(use_dsg_tiebreak ? "acik" : "kapali") + "\n");

    auto build_result = [&](const std::vector<MoveRecord>& path, double secs,
                            long long nodes, int iters) -> py::object {
        py::gil_scoped_acquire gil;
        py::list py_moves, py_h, py_f, py_g;
        py_h.append(root.h);  py_f.append(root.f);  py_g.append(0);
        for (const auto& m : path) {
            py_moves.append(py::make_tuple(m.src_lane, m.src_slot, m.dst_lane, m.dst_slot,
                                           m.item, m.g, m.h, m.f, m.time_sec));
            py_h.append(m.h);  py_f.append(m.f);  py_g.append(m.g);
        }
        py::dict res;
        res["num_moves"]      = (int)path.size();
        res["moves"]          = py_moves;
        res["time"]           = secs;
        res["h_values"]       = py_h;
        res["f_values"]       = py_f;
        res["g_values"]       = py_g;
        res["nodes_expanded"] = nodes;
        res["iterations"]     = iters;
        return res;
    };

    if (root.total_blocking == 0)
        return build_result({}, 0.0, 0, 0);

    // ── Worker sayısı ───────────────────────────────────────────────────────
    unsigned hw = std::thread::hardware_concurrency();
    int worker_count = num_threads > 0 ? num_threads : (hw > 0 ? (int)hw : 1);
    worker_count = std::max(1, worker_count);

    // ── Paylaşılan durum ────────────────────────────────────────────────────
    std::atomic<double> threshold(root.h);
    std::atomic<double> min_exceeded(std::numeric_limits<double>::infinity());
    std::atomic<bool>   found(false);
    std::atomic<bool>   stop_requested(false);

    WorkQueue work_queue;
    std::deque<WorkItem> root_items = build_root_work_items(root, L, use_dsg_tiebreak);
    if (root_items.empty()) {
        log("Cozum bulunamadi.\n");
        py::gil_scoped_acquire gil;
        return py::none();
    }

    std::mutex solution_mutex;
    std::vector<MoveRecord> solution_path;
    std::vector<ThreadStats> stats(worker_count);

    int       iteration   = 0;
    long long total_nodes = 0;

    // ── Ana döngü: her tur tam bir IDA* iterasyonu (fork → join) ────────────
    while (true) {
        if (check_stop() || check_stop_get_best()) {
            log("IDA* durduruldu, None donuluyor.\n");
            py::gil_scoped_acquire gil;
            return py::none();
        }

        iteration++;
        {
            std::lock_guard<std::mutex> lock(work_queue.mutex);
            work_queue.items = root_items;
        }
        min_exceeded.store(std::numeric_limits<double>::infinity(), std::memory_order_release);
        for (auto& st : stats) st.min_h_seen = root.h;

        log("Iterasyon " + std::to_string(iteration)
            + " | esik=" + std::to_string(threshold.load())
            + " | " + std::to_string(worker_count) + " thread aciliyor\n");

        // ── FORK: worker'ları başlat ────────────────────────────────────────
        std::vector<std::thread> workers;
        workers.reserve(worker_count);
        for (int id = 0; id < worker_count; ++id) {
            workers.emplace_back([&, id]() {
                log("Thread " + std::to_string(id) + " acildi\n");

                ThreadStats& st = stats[id];
                WorkItem work;
                bool got_any = false;
                while (work_queue.pop(work)) {
                    got_any = true;
                    if (found.load(std::memory_order_acquire) ||
                        stop_requested.load(std::memory_order_acquire))
                        break;

                    std::vector<MoveRecord> local_path = std::move(work.path_prefix);
                    double result = dfs(work.node, L, threshold, min_exceeded,
                                        found, stop_requested, iteration,
                                        local_path, st, work.init_dsg, use_dsg_tiebreak,
                                        t_start, log, check_stop);

                    if (result == IDA_FOUND) {
                        bool expected = false;
                        if (found.compare_exchange_strong(expected, true)) {
                            std::lock_guard<std::mutex> lock(solution_mutex);
                            solution_path = std::move(local_path);
                        }
                        work_queue.clear();
                        break;
                    }
                    if (result == IDA_STOP) {
                        stop_requested.store(true, std::memory_order_release);
                        work_queue.clear();
                        break;
                    }
                }

                if (!got_any)
                    log("Thread " + std::to_string(id) + " bosta kaldi (hic is alamadi)\n");
            });
        }

        // ── JOIN: tüm worker'lar bitene kadar bekle ─────────────────────────
        for (auto& w : workers) w.join();

        total_nodes = 0;
        for (const auto& st : stats) total_nodes += st.nodes_expanded;

        // ── İterasyon sonucu değerlendir ────────────────────────────────────
        if (stop_requested.load(std::memory_order_acquire)) {
            log("IDA* durduruldu (dfs icinde), None donuluyor.\n");
            py::gil_scoped_acquire gil;
            return py::none();
        }

        if (found.load(std::memory_order_acquire)) {
            auto t_end = std::chrono::steady_clock::now();
            double secs = std::chrono::duration<double>(t_end - t_start).count();
            std::vector<MoveRecord> path;
            { std::lock_guard<std::mutex> lock(solution_mutex); path = solution_path; }
            log("Cozum bulundu! adim=" + std::to_string((int)path.size())
                + " iter=" + std::to_string(iteration)
                + " sure=" + std::to_string(secs) + "\n");
            return build_result(path, secs, total_nodes, iteration);
        }

        double next = min_exceeded.load(std::memory_order_acquire);
        if (next == std::numeric_limits<double>::infinity()) {
            auto t_end = std::chrono::steady_clock::now();
            double secs = std::chrono::duration<double>(t_end - t_start).count();
            log("Cozum bulunamadi. sure=" + std::to_string(secs) + "\n");
            py::gil_scoped_acquire gil;
            return py::none();
        }

        threshold.store(next, std::memory_order_release);
    }
}

// ── Pybind11 modülü ──────────────────────────────────────────────────────────

PYBIND11_MODULE(ida_star_cpp, m) {
    m.def("ida_star_cpp", &ida_star,
          py::arg("lanes"),
          py::arg("log_fn")           = py::none(),
          py::arg("stop_get_best_fn") = py::none(),
          py::arg("stop_fn")          = py::none(),
          py::arg("use_dsg_tiebreak") = false,
          py::arg("num_threads")      = 8,
          py::call_guard<py::gil_scoped_release>()
    );
}