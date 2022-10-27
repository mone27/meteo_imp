# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/99_utils.ipynb.

# %% auto 0
__all__ = ['cache_disk']

# %% ../lib_nbs/99_utils.ipynb 1
# dill is an improved version of pickle, using it to support namedtuples
import dill
from pathlib import Path

# %% ../lib_nbs/99_utils.ipynb 2
# inspired from https://gist.github.com/shantanuo/c6a376309d6bac6bd55bf77e3961b5fb
def cache_disk(base_file):
    base_file = Path(base_file)
    def decorator(original_func):
        
        # take the hash of the function content
        filename = base_file.parent / (base_file.stem + str(hash(original_func.__code__.co_code)) + ".pickle")
        
        try:
            cache = dill.load(open(filename, 'rb'))
        except (IOError, ValueError):
            cache = {}

        def save_data():
            dill.dump(cache, open(filename, "wb"))  

        def new_func(*args):
            if tuple(args) not in cache:
                cache[tuple(args)] = original_func(*args)
                save_data()
            return cache[args]

        return new_func

    return decorator
