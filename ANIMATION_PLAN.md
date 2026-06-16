# UPMP Animation Plan

Bu dosya `from UPMP import Animation` fonksiyonunun nihai hedefini ve mevcut
iskeletin ne yaptigini not eder.

## Paketleme

Animasyon icin `PySide6` ve `vtk` agir GUI bagimliliklari gerekir. Bu yuzden
normal kurulumda zorunlu degiller.

Solver icin:

```bash
pip install UPMP
```

Animasyon penceresi icin:

```bash
pip install UPMP[animation]
```

`pyproject.toml` icinde bu bagimliliklar `animation` optional dependency grubu
altinda tutulur.

## Mevcut Iskelet

`Animation()` su an PySide6 penceresi acar ve bu pencerenin icine VTK render
alani gomerek gosterir. `ida_result`, `depo` ve `lanes` birlikte verilirse
raw C++ lane/slot sonucu fiziksel hucrelere cevrilir ve ilk depo state'i basit
VTK kupleri olarak cizilir. Fonksiyon herhangi bir deger dondurmez.

Kullanim:

```python
from UPMP import Animation

Animation()
```

Ilk depo sahnesini cizmek icin:

```python
from UPMP import Animation, accessDirectionFixing, idaStar, stackAreaGenerator

depo = stackAreaGenerator(4, 4, 3, fill_pct=60, access="NW", seed=1)
lanes, lane_matrix = accessDirectionFixing(depo)
result = idaStar(lane_matrix)

Animation(result, depo, lanes, lane_matrix)
```

## Nihai Hedef

Nihai fonksiyon `idaStar` sonucunu alacak, fakat raw `idaStar` sonucu tek
basina yeterli degildir. C++ sonucu sanal `lane/slot` bilgisi dondurur. VTK
animasyonu icin gercek depo hucreleri ve blok yukseklikleri gerekir.

Bu yuzden nihai API su sekilde dusunulmelidir:

```python
from UPMP import stackAreaGenerator, accessDirectionFixing, idaStar, Animation

depo = stackAreaGenerator(...)
lanes, lane_matrix = accessDirectionFixing(depo)
result = idaStar(lane_matrix)

Animation(
    ida_result=result,
    depo=depo,
    lanes=lanes,
    lane_matrix=lane_matrix,
    speed=1.0,
    show_routes=True,
)
```

## Yapilacak Ana Isler

1. `ida_result["moves"]` icindeki `src_lane/src_slot/dst_lane/dst_slot`
   bilgisini `lanes` ve `depo` yardimiyla gercek `(x, y, z)` hucrelerine
   cevirmek.
2. Her hamleden sonra depo state matrisini yeniden uretmek.
3. Ana uygulamadaki rota mantigiyla `approach_main_route` ve
   `carry_main_route` planlarini uretmek.
4. VTK sahnesine ilk depo state'ini blok aktorleri olarak basmak.
5. Forklift, catal ve blok tasima animasyonunu PySide6 timer ile calistirmak.
6. Hizi degistirmek icin slider eklemek.
7. Duraklat/devam et, durdur ve rota goster/gizle kontrollerini eklemek.

## Ana Uygulamadan Animasyon Uyarlama Plani

Ana uygulamadaki animasyon kodu dogrudan kopyalanmayacak. Bunun yerine
`RouteAnimation` motoru kullanilip `ida-star-cpp/UPMP` icindeki basit VTK
sahnesine uyan kucuk bir adaptasyon katmani kurulacak.

### Kullanilacak Ana Parcalar

- `engine.pathfinding.animation.RouteAnimation`
  - Forklift aktorunu olusturur.
  - Catal seviyesini hareket ettirir.
  - Blok alma, tasima ve birakma animasyonunu calistirir.
  - `toggle_pause()` ile duraklat/devam ettirir.
- `engine.pathfinding.animation_bridge`
  - `rebuild_step_plans_like_pathfinding_deneme(...)`
  - `build_anim_moves_from_plans(...)`
  - `apply_time_params(...)`
  - `calculate_plan_times_from_animation(...)`
- `UPMP.simple_scene.SimpleVTKScene`
  - Depo zeminini, padding alanini, bloklari, rota overlay'ini, erisim
    yonlerini ve hamle highlight'larini cizer.

### Veri Akisi

1. `Animation(...)` icinde zaten olusan veriler kullanilacak:
   - `states_frozen`
   - `moves`
   - `move_directions`
   - `lanes`
2. `rebuild_step_plans_like_pathfinding_deneme(...)` ile her hamle icin
   `route_plans` uretilecek.
3. Animasyon baslatilirken secilen baslangic adimina gore `route_plans`
   kirpilacak.
4. `build_anim_moves_from_plans(...)` ile `RouteAnimation.run(...)` icin
   move dict listesi hazirlanacak.
5. `Forklift Sureleri` panelindeki degerler `apply_time_params(...)` ile
   `RouteAnimation.time_parameters` alanina aktarilacak.
6. Geri cekilme cezasi kullanilmayacak. Geri geri gidilen gercek rota
   mesafesi zaten `duz seyahat` suresiyle hesaplanacak.

### Koordinat Uyumu

`SimpleVTKScene` depo hucrelerini padding ile cizer. Varsayilan padding `5`.
Bu nedenle grid koordinati `(x, y)` sahnede `(x + padding, y + padding)`
olarak gorunur.

`RouteAnimation` ise grid koordinatlarinda calismayi bekler. Bu yuzden
animasyon baslatilirken iki secenekten biri uygulanmali:

1. `route_plans` ve animasyon move koordinatlari padding kadar kaydirilir.
2. `RouteAnimation` tarafina world origin/padding benzeri bir ofset verilir.

Mevcut `RouteAnimation` constructor'i yalnizca `step_plans` ve
`nudge_distance` aliyor. Bu nedenle ilk uygulamada daha az riskli yol:

- Animasyona verilen `step_plans` ve `anim_moves` padding kadar kaydirilsin.
- Blok aktorleri de `(x + padding, y + padding, z)` anahtarlariyla toplansin.
- UI'daki rota/highlight overlay'leri grid koordinatinda kalmaya devam etsin;
  sadece animasyon motoruna giden input kaydirilsin.

### Blok Aktorleri

`RouteAnimation` bloklari `(x, y, z)` anahtariyla bulup actor'u
`SetPosition(...)` ile tasir.

`SimpleVTKScene` su anda bloklari `vtkCubeSource.SetCenter(...)` ile ciziyor.
Bu, gorsel olarak dogru olsa da animasyon icin dikkat gerektirir:

- Aktorun baslangic `Position` degeri sifir olabilir.
- `RouteAnimation` actor'u tasirken `SetPosition(...)` kullanir.
- Bu nedenle animasyona baslamadan once blok aktorlerinin `RouteAnimation`
  beklentisine uygun sekilde indexlenmesi gerekir.

Ilk uygulama icin `SimpleVTKScene` icine kucuk yardimcilar eklenebilir:

- `collect_anim_block_actors()`
  - Aktif blok aktorlerini `(scene_x, scene_y, phys_z)` anahtariyla dondurur.
- `clear_animation_artifacts()`
  - Forklift, yon noktalari ve yarim kalmis tasinan blok gibi animasyon
    kalintilarini temizler.
- `render_state(..., reset_camera=False)`
  - Animasyon iptalinde veya bitisinde sahneyi ilgili state'e snapler.

Gerekirse blok cizimi daha sonra actor merkezini geometri icinde degil,
actor `SetPosition` ile verecek sekilde sade hale getirilebilir. Bu,
`RouteAnimation` ile en temiz uyumdur.

### UI Davranisi

Sag paneldeki mevcut butonlar kullanilacak:

- `Bastan Sona Canlandir`
  - `from_step = 0` ile tum animasyonu baslatir.
- `Secili Adimdan Canlandir`
  - Sol adim listesindeki secili adimdan baslatir.
  - Secili satir `0` ise ilk hamleden baslar.
  - Secili satir `i` ise `moves[i - 1]` hamlesinden baslatir.
- `Duraklat`
  - Aktif animasyon varsa `RouteAnimation.toggle_pause()` cagirir.
  - Buton metni `Devam Et` / `Duraklat` olarak degisir.
- `Iptal`
  - Timer'i durdurur.
  - Forklift ve animasyon kalintilarini temizler.
  - Sahneyi secili state'e geri snapler.

Animasyon calisirken:

- `Bastan Sona Canlandir` ve `Secili Adimdan Canlandir` pasif olur.
- `Duraklat` ve `Iptal` aktif olur.
- Hiz slider'i `anim.speed` degerini gunceller.

### Sureler

Ilk surumde sure muhasebesi basit tutulacak:

1. Animasyon oncesi `calculate_plan_times_from_animation(...)` ile
   `move_times` ve `move_time_details` hesaplanir.
2. `time_reverse_penalty` her zaman `0.0` kabul edilir.
3. Canli sure label'lari ilk etapta zorunlu degil.
4. `Sure Logu` penceresi ayni hesaplanan veriyi kullanir.

Daha sonra ikinci asamada:

- Aktif komut metni `anim._active_cmd` uzerinden `anim_phase` label'ina
  yansitilabilir.
- 100 ms'lik `QTimer` ile adim simulasyon/gercek sure label'lari
  guncellenebilir.
- Animasyon tamamlandiginda toplam sure ozeti `anim_summary` alanina yazilabilir.

### Rota ve Erisim Overlay'leri

Ilk uygulamada overlay'ler animasyonu bloklamamali:

- `Rotayi Goster` aciksa, secili/aktif adimin rota overlay'i cizili kalabilir.
- Animasyon step degistirdikce rota overlay'ini aktif hamleye senkronlamak
  ikinci asamaya birakilabilir.
- `Erisim Yonlerini Goster` aciksa, state degistikce erisim oklari
  guncellenebilir; ilk surumde animasyon basinda mevcut state'e gore kalmasi
  kabul edilebilir.

### Baslangic Algoritmasi

Animasyon baslatma fonksiyonu genel olarak su sirayla ilerlemeli:

1. Devam eden animasyon varsa temizle.
2. `from_step` degerini hesapla.
3. Sahneyi `states[from_step]` ile yeniden ciz.
4. `route_plans[from_step:]` listesini al.
5. Animasyon motoruna verilecek planlari padding kadar kaydir.
6. `build_anim_moves_from_plans(...)` ile move dict listesini olustur.
7. Sahnedeki blok aktorlerini animasyon koordinatlarina gore topla.
8. `RouteAnimation(step_plans=shifted_plans)` olustur.
9. `apply_time_params(anim, time_params)` uygula.
10. `anim.speed = speed_slider.value() / 5.0` ata.
11. `anim.run(renderer, anim_moves, current_idx=1, block_actors=block_actors)`
    cagir.
12. UI buton durumlarini animasyon calisiyor haline getir.

### Bitis Algoritmasi

Animasyon bittiginde:

1. Animator timer'i durdurulur.
2. Forklift ve gecici yon noktalari temizlenir.
3. Son hamleden sonraki state hesaplanir:
   - Bastan sona basladiysa final `states[-1]`.
   - Secili adimdan basladiysa `states[from_step + oynanan_hamle_sayisi]`.
4. Sahne bu state ile tekrar cizilir.
5. Sol adim listesi final state'e ilerletilir.
6. Butonlar normal hale getirilir.
7. Kamera sifirlanmaz.

### Iptal Algoritmasi

Kullanici `Iptal` derse:

1. Animator timer'i durdurulur.
2. Forklift ve gecici animasyon aktorleri temizlenir.
3. Sahne sol panelde secili olan state'e snaplenir.
4. Rota/erisim/highlight toggle'lari mevcut durumlarina gore tekrar cizilir.
5. Butonlar normal hale getirilir.

### Ilk Uygulama Kapsami

Ilk kodlama turunda hedef:

- Bastan sona animasyon
- Secili adimdan animasyon
- Duraklat/devam et
- Iptal
- Hiz slider'i
- Bitince final state'e snap
- Geri cekilme cezasi olmadan sure parametreleri

Bu turda ertelenebilecekler:

- Canli detayli sure label'lari
- Her animasyon step'inde rota overlay senkronu
- Her animasyon step'inde erisim yonu oklari senkronu
- Gelismis hata/uyari paneli
