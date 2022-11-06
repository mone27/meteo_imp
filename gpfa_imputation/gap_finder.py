# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/20_gap_finder.ipynb.

# %% auto 0
__all__ = ['find_gap', 'scan_fluxnet_csv', 'get_site_info', 'find_gaps_fluxnet_archive', 'download_fluxnet', 'find_all_gaps',
           'download_and_find_gaps']

# %% ../lib_nbs/20_gap_finder.ipynb 2
import polars as pl
import zipfile
from pathlib import Path
import requests
import re
from tqdm.auto import tqdm

# %% ../lib_nbs/20_gap_finder.ipynb 24
def find_gap(df, col_name):
    return df.select(
        [col_name, pl.col("TIMESTAMP_END").alias("gap_start")]
    ).with_column(
        pl.first().cumcount().alias("row_num")
    ).filter(
        pl.col(col_name) != 0
    ).with_columns([
        (pl.col("row_num") - pl.col("row_num").shift() ).alias("before"),
        (pl.col("row_num").shift(-1) - pl.col("row_num")).alias("after"),
    ]).filter(
        (pl.col("before") != 1) | (pl.col("after") != 1)
    ).with_column(
        (pl.when((pl.col("before") != 1) & (pl.col("after") != 1))
        .then(pl.col("gap_start"))
        .otherwise(pl.col("gap_start").shift(-1))
        .alias("gap_end"))
    ).filter(
        pl.col("before") != 1
    ).select(
        ["gap_start", "gap_end", pl.lit(col_name).alias("variable")]
    )

# %% ../lib_nbs/20_gap_finder.ipynb 25
def scan_fluxnet_csv(f, convert_dates=False):
    
    # col names may be different between the stations, so read them from the csv before parsing the whole file
    col_names = pl.read_csv(f, n_rows=1).columns
        
    types = {
        **{
            # pl.Uint8 should be enough for a QC flag, but some columns are floats in the csv ...
            col_name: pl.Float32 if col_name.endswith("_QC") else pl.Float64 for col_name in col_names
        },
        "TIMESTAMP_START": pl.Int64, # for now keep as int convert to dates at the end
        "TIMESTAMP_END": pl.Int64
    } 
    
    df = pl.scan_csv(
        f, null_values=["-9999", "-9999.99"], dtypes=types
        ).rename({
            "TIMESTAMP_START": "start",
            "TIMESTAMP_END": "end", 
        })
    
    if convert_dates:
        df = df.with_columns([
            pl.col("start").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y%m%d%H%M"),
            pl.col("end").cast(pl.Utf8).str.strptime(pl.Datetime, "%Y%m%d%H%M"),
        ])
        
    return df       

# %% ../lib_nbs/20_gap_finder.ipynb 27
def get_site_info(df):
    return df.select([
        pl.col("start").first(),
        pl.col("end").last()
    ]).collect()

# %% ../lib_nbs/20_gap_finder.ipynb 28
def _get_site_url(url): return re.search(r"[A-Z]{2}-[A-z0-9]{3}", url).group()
    
def find_gaps_fluxnet_archive(path_zip, # zip file path that uses fluxnet 
                  out_dir,
                  tmp_dir,
                  delete_file = True
                         ):
    try:
        fname = path_zip.stem.replace("FULLSET", "FULLSET_HH") 
        out_name = out_dir / f"GAPS_stat_{fname}.parquet"
        f = zipfile.ZipFile(path_zip).extract(fname + ".csv", path=tmp_dir)
    except KeyError:
        fname = path_zip.stem.replace("FULLSET", "FULLSET_HR") # some sites are naed differently
        out_name = out_dir / f"GAPS_stat_{fname}.parquet"
        f = zipfile.ZipFile(path_zip).extract(fname + ".csv", path=tmp_dir)
    
    df = scan_fluxnet_csv(f)
    
   
    
    gaps = find_all_gaps(df).collect()
    
    # site info
    site = _get_site_url(fname)
    site_info = get_site_info(df, site)
    
    gaps = gaps.with_column(
        pl.lit(site_info[0, "site_start"]).alias("site_start"),
        pl.lit(site_info[0, "site_end"]).alias("site_end"),
        pl.lit(site).alias("site"),
    )
    
    # convert dates to correct type
    gaps = gaps.with_column(
       pl.col("start").str.strptime(pl.Datetime, "%Y%m%d%H%M"), 
       pl.col("end").str.strptime(pl.Datetime, "%Y%m%d%H%M"), 
    )
    
    gaps.write_parquet(out_name)
    
    if delete_file: Path(f).unlink()
    
    return fname, site_info

# %% ../lib_nbs/20_gap_finder.ipynb 37
def download_fluxnet(url, download_dir):
    
    
    file_name = download_dir / re.search(r"([^/]*)\?", url).group()[:-1] 
    
    if file_name.exists(): return file_name
    
    n_iter = int(requests.head(url).headers['Content-Length']) / 1024
    r = requests.get(url, allow_redirects=True, stream=True)
    n_iter = int(r.headers['Content-Length'])
    with open(file_name, 'wb') as file:
        with tqdm(total=n_iter, unit_divisor=1024, unit_scale=True, unit='B') as pbar:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
                    pbar.set_postfix(site=file_name.name[:10], refresh=False)
                    pbar.update(1024) # one chunck
    
    return file_name

# %% ../lib_nbs/20_gap_finder.ipynb 44
def find_all_gaps(df):
    return pl.concat(
        [find_gap(df, col_name) for col_name in df.select(pl.col("^.*_QC$")).columns]
    )

# %% ../lib_nbs/20_gap_finder.ipynb 48
def download_and_find_gaps(urls, download_dir, out_dir, tmp_dir):
    site_infos = []
    for url in tqdm(urls):
        file_zip = download_fluxnet(url, download_dir)
        file, site_info = find_gaps_fluxnet_archive(file_zip, out_dir, tmp_dir)
        site_infos.append(site_info)
        print(file)
        
    return pl.concat(site_infos)
