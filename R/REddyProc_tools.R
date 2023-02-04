#' Fill gaps using EddyProc
#' dataset should contain a column called `gap` which is 0 where there is not gap and 1 wehre there is a gap
#' @param data
#' @param var character of variable to be gap-filled
fill_gaps_EProc <- function(data, var, V_names = default_V_vars, T_values = default_T_values){
  stopifnot(all(c("V1" , "V2", "V3") %in% names(V_names)))
  stopifnot(all(c("T1" , "T2", "T3") %in% names(T_values)))
  EProc <- REddyProc::sEddyProc$new("ID", Data = data, ColNames = names(select(data, -TIMESTAMP_END)), ColPOSIXTime = "TIMESTAMP_END")
  rlang::inject(EProc$sMDSGapFill(var, QFVar = "gap", QFValue = 0, !!!V_names, !!!T_values, FillAll = FALSE))
  EProc$sExportResults()
}

default_V_vars <- list(
  V1 = "SW_IN",
  V2 = "VPD",
  V3 = "Tair"
)

default_T_values <- list(
  T1 = 50,
  T2 = 5,
  T3 = 2.5
)


#' Creates a random gap of given length and fill it
#' @param use_vars other variable to remove
gap_fill_random_gap_EProc <- function(data, var, gap_length, use_vars = list(names = default_V_vars, values = default_T_values)) {

  data_gap <- data %>%
    mutate(gap = random_gap(gap_length, nrow(data)))

  filled <- data_gap %>%
    # remove_var_gap(use_vars) %>%
    fill_gaps_EProc(var, use_vars$names, use_vars$values)

  data_filled <- bind_cols(data_gap, filled) %>%
    filter(gap !=0 ) # the interesting part is only where there is the gap

  tibble(gap_length = gap_length, data = list(data_filled))
}

#' Vectorized version of gap legths
gap_fill_random_gap_EProc_vec <- function(data, var, gap_lengths, use_vars = list(names = default_V_vars, values = default_T_values)){
  map_dfr(gap_lengths, ~gap_fill_random_gap_EProc(data, var, .x, use_vars))
}


#' Set to NA the given variables in the gap
remove_var_gap <- function(data, remove_vars){
  data[as.logical(data$gap), remove_vars] <-  NA
  print(colSums(is.na(data)))
  data
}

#' generate random gaps of for the given lengths and then fills them with
gap_fill_multiple_gaps_EProc <- function(site_data, gaps_lengths, var, n_workers = 4, use_vars = list(names = default_V_vars, values = default_T_values)){
  suppressWarnings({
    suppressMessages({
        gaps_lengths %>%
          split_vector(n_workers) %>%
          future_map(~gap_fill_random_gap_EProc_vec(site_data, var, .x, use_vars), .options = furrr_options(seed = TRUE)) %>%
          bind_rows() %>%
          mutate(
            rmse = map_dbl(data, ~gap_rmse(.x, var))
          )
    })
  })
}



#' calculate RMSE or gap filled data
#' @param data
#' @param var variable to gap fill
gap_rmse <- function(data, var){
  rmse(pull(data, !!sym(var)), pull(data, !!sym(str_glue("{var}_f"))))
}

pretty_gap_len <- function(gap_length){
  str_glue("{prettyunits::pretty_dt(as.difftime(gap_length * 30, units=\"mins\"))} ({gap_length} obs.)")

}
