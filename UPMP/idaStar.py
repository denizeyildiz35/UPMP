import ida_star_cpp


def idaStar(
    lanes,
    log_fn=None,
    stop_get_best_fn=None,
    stop_fn=None,
    use_dsg_tiebreak=False,
    num_threads=8,
):
    return ida_star_cpp.ida_star_cpp(
        lanes,
        log_fn=log_fn,
        stop_get_best_fn=stop_get_best_fn,
        stop_fn=stop_fn,
        use_dsg_tiebreak=use_dsg_tiebreak,
        num_threads=num_threads,
    )


solve = idaStar
