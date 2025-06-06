# tamriaelchemy
python library and utilities for mastering alchemy in tamriel

currently supports Oblivion and Skyrim with all official expansion packs but can be expanded to use ingredients in other mods.

## Basic usage

    skyrim = Skyrim.create()
    ingredient_lab = skyrim.ilab()
    ingredient_lab.stat
    ingredient_lab.add("Wheat").add("Taproot").add("Torchbug Thorax").stat
    ingredient_lab.pivot().recipes

## Oblivion

Enumerating Oblivion is slow. This is due to the exponentially larger selection of ingredients and combinations compared to skyrim. When you create an alchemist with `Oblivion.create()` the entire collection of possible potions and recipes is calculated and cached into a compressed file. Even after creating this the first time and loading from the cache, it can be very slow and uses a lot of memory.

## Database

A database may be included or usable for a cache in the future depending on speed and disk space.