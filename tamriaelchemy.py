from collections.abc import Iterable, Iterator
from collections import defaultdict
from csv import DictReader
from itertools import combinations
from functools import reduce
from types import NotImplementedType
from typing import Iterable, List, Self, Set, Dict, Hashable, FrozenSet, SupportsIndex, Callable, Any, Optional
from uuid import UUID, uuid4
from enum import Enum, IntEnum
from pathlib import Path
import json
import lzma


class InvalidAlchemistSetting(Exception):
    pass


class Mastery(IntEnum):
    NOVICE = 0
    APPRENTICE = 1
    JOURNEYMAN = 2
    EXPERT = 3
    MASTER = 4
    

class Effect:
    name: str
    status: int
    _db_id: int
    _alch_id: UUID
    
    def __init__(self, name: str, status: int = 0):
        self.name = name
        self.status = status
        self._db_id = -1
        self._alch_id = None #uuid4()

    def to_dict(self):
        return {"name": self.name,
                "status": self.status}
    
    def as_tuple(self):
        return (self.name, self.status)

    @classmethod
    def from_dict(cls, effect: dict):
        return cls(name=effect['name'], status=effect['status'])
    
    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f"{self.name} ({self.status})"


class Ingredient:
    source: str
    name: str
    game_id: str
    _effects: dict[int, str]
    value: int
    weight: float
    _level: int
    _fxset: set[str]
    _max_effects: int = 4
    _db_id: int
    _alch_id: UUID|None
    
    @classmethod
    def from_dict(cls, d: dict):
        return cls(d['name'], d['source'], d['game_id'], d['weight'], d['value'], 
                   d['primary'], d['secondary'], d['tertiary'], d['quaternary'])
    
    def __init__(self, name: str, source: str, game_id: str, weight: float, value: int,
                 primary: str, secondary: str, tertiary: str, quaternary: str):
        self.source = source.strip()
        self.name = name.strip()
        self.game_id = game_id
        self.value = int(value)
        self.weight = float(weight)
        self._fxset = None
        self._effects = dict()
        self._db_id = -1
        self._alch_id = None #uuid4()
        
        self._effects[0] = primary.strip() if isinstance(primary, str) else None
        self._effects[1] = secondary.strip() if isinstance(secondary, str) else None
        self._effects[2] = tertiary.strip() if isinstance(tertiary, str) else None
        self._effects[3] = quaternary.strip() if isinstance(quaternary, str) else None
        
        self._level = 0
        for i in range(0, 4):
            fx = self._effects[i]
            if fx is not None and len(fx) > 0:
                self._level = i
            else:
                break

    def to_dict(self) -> dict:
        return {'name':self.name, 
                'source':self.source, 
                'game_id':self.game_id, 
                'value':self.value, 
                'weight':self.weight,
                'primary':self._effects[0], 
                'secondary':self._effects[1], 
                'tertiary':self._effects[2], 
                'quaternary':self._effects[3]}

    @property
    def key(self) -> Hashable:
        return self.name
    
    @property
    def level(self) -> int:
        return self._level
    
    @level.setter
    def level(self, lvl: int):
        n = int(lvl)
        if n in Mastery:
            self._level = n
            self._gen_effects()
        else:
            raise ValueError("Valid levels are 0 (NOVICE) to 4 (MASTER)")
    
    def __add__(self, other):
        if isinstance(other, Ingredient):
            return Potion([self, other])
        elif isinstance(other, Potion):
            return other.__add__(self)
        else:
            raise TypeError(f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'")
    
    @property
    def effects(self) -> set:
        if self._fxset is None:
            self._gen_effects()
        return self._fxset
    
    def _gen_effects(self):
        """create internal set of effects based on max level (0-4)
        """
        self._fxset = set()
        for k,v in self._effects.items():
            if v is not None and len(v) > 0 and k <= self._level:
                self._fxset.add(v)
    
    def common_effects(self, ingredient)-> bool | NotImplementedType:
        if not isinstance(ingredient, Ingredient):
            return NotImplemented
        return self.effects & ingredient.effects

    def add_effect(self, effect: str) -> bool:
        k = len(self._effects)
        if k < self._max_effects:
            self._effects[k] = effect
            self._gen_effects()
            return True
        return False
        
    def __repr__(self) -> str:
        return ",".join(self.as_tuple())
    
    def as_tuple(self) -> tuple[str]:
        # (source,name,id,primary,secondary,tertiary,quaternary,weight,value)
        return (self.source, self.name, self.game_id, 
                self._effects[0], self._effects[1], self._effects[2], self._effects[3], 
                str(self.weight), str(self.value))

    def __eq__(self, other) -> bool | NotImplementedType:
        if not isinstance(other, Ingredient):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()
    
    def __str__(self) -> str:
        return self.name
    
    def __hash__(self) -> int:
        return hash(self.as_tuple())

    def get_effect(self, level: int):
        return self._effects.get(level)

    @property
    def primary(self):
        return self._effects.get(0)

    @property
    def secondary(self):
        return self._effects.get(1)
    
    @property
    def tertiary(self):
        return self._effects.get(2)
    
    @property
    def quaternary(self):
        return self._effects.get(3)

    
class IngredientCollection:
    collection: List[Ingredient]
    ingredient_map: Dict[str,Ingredient]
    effect_map: Dict[str,set[str]]
    sources: set[str]
    _mastery: Mastery
    
    def __init__(self, collection: Iterable[Ingredient] | None = None, mastery: Mastery = Mastery.EXPERT):
        self.sources = set()
        self.collection = list(collection) if collection else list()
        self.ingredient_map = dict()
        self.effect_map = defaultdict(lambda: set())
        self._mastery = mastery
        self.catalog_ingredients()
    
    @property
    def mastery(self) -> Mastery:
        return self._mastery
    
    @mastery.setter
    def mastery(self, setting: Mastery):
        if not isinstance(setting, Mastery):
            raise TypeError("Invalid mastery setting.")
        self._mastery = setting
        self.catalog_ingredients()
    
    def add(self, ingredient: Ingredient):
        ingredient.level = self._mastery
        self.collection.append(ingredient)
        self._catalog(ingredient=ingredient)
    
    def catalog_ingredients(self):
        self.effect_map.clear()
        self.ingredient_map.clear()
        self.sources.clear()
        for i in self.collection:
            i.level = self._mastery
            self._catalog(ingredient=i)
    
    def _catalog(self, ingredient: Ingredient):
        src = ingredient.source
        if isinstance(src, str) and len(src) > 0:
            self.sources.add(src)
        self.ingredient_map[ingredient.key] = ingredient
        for f in ingredient.effects:
            if len(f) > 0:
                self.effect_map[f].add(ingredient.key)
    
    def lookup(self, ingredient_key: str) -> Ingredient|None:
        return self.ingredient_map.get(ingredient_key)
    
    def effects(self) -> frozenset[str]:
        return frozenset(self.effect_map.keys())
    
    def with_effects(self, effects: Iterable[str]) -> frozenset[str]:
        ingrd_keys: set[str] = set()
        for effect in effects:
            ingrd_keys.update(self.effect_map.get(effect, set()))
        return frozenset(ingrd_keys)
    
    def with_effect(self, effect: str) -> set[str]:
        return self.effect_map.get(effect, set())
    
    @classmethod
    def from_csv(cls, file: str, mastery: Mastery = Mastery.EXPERT) -> Self:
        return cls(collection=cls.enum_csv(file=file), mastery=mastery)
    
    @staticmethod
    def enum_csv(file: str) -> Iterator[Ingredient]:
        with open(file, 'rt') as csvfile:
            reader = DictReader(csvfile)
            for row in reader:
                yield Ingredient.from_dict(row)
    
    @classmethod
    def from_json(cls, file: str, mastery: Mastery = Mastery.EXPERT) -> Self:
        return cls(collection=cls.enum_json(file=file), mastery=mastery)
    
    @staticmethod
    def enum_json(file: str) -> Iterator[Ingredient]:
        with open(file, 'rt') as jsonfile:
            j = json.load(jsonfile)
        if isinstance(j, dict):
            inglist = j.get('ingredients', [])
        elif isinstance(j, list):
            inglist = j
        else:
            return
        for d in inglist:
            yield Ingredient.from_dict(d)

    def enum_combos(self, imin: int = 2, imax: int = 3) -> Iterator[tuple[Ingredient]]:
        for i in range(imin, imax + 1):
            for combo in combinations(self.collection, i):
                yield combo


class Potion(object):
    ingredients: Dict[str,Ingredient]
    effects: Set[str]
    _weight: float|None
    _value: int|None
    _mixed: bool
    _checked: bool
    _ing_key: FrozenSet[str]
    _fx_key: FrozenSet[str]
    _db_id: int
    _alch_id: UUID
    
    @classmethod
    def from_ingredients(cls, ingredients: Iterable[Ingredient]):
        p = cls(ingredients)
        if p.mix().check():
            return p
        else:
            return None
    
    def __add__(self, other: Self|Ingredient):
        if not isinstance(other, Ingredient):
            raise TypeError(f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'")
        
        if other.key not in self.ingredients:
            if self.mixed:
                pot = Potion(self.ingredients.values())
                pot.add_ingredient(other)
                return pot
            else:
                self.add_ingredient(ingredient=other)
                
        return self
    
    def test_with(self, other: Ingredient) -> Self|None:
        if other.key in self.ingredients:
            return None
        fxlist = [ing.effects for ing in self.ingredients.values()]
        fxlist.append(other.effects)
        new_fx = self.multi_intersect(fxlist)
        if new_fx == self.effects:
            return None
        pot = Potion(self.ingredients.values())
        pot.add_ingredient(other)
        pot.effects = new_fx
        pot._mixed = True
        pot._checked = None
        return pot
    
    def __init__(self, ingredients: Iterable[Ingredient]):
        self._mixed = False
        self._checked = None
        self.effects = set()
        self.ingredients = dict()
        self._fx_key = None
        self._ing_key = None
        self._weight = None
        self._value = None
        self._db_id = -1
        self._alch_id = None #uuid4()
        
        for ing in ingredients:
            self.add_ingredient(ing)

    def __str__(self):
        ings = " + ".join(sorted(self.ingredients.keys()))
        
        if not self._mixed:
            return ings
        
        if len(self.effects) == 0:
            fx = "None"
        else:
            fx = " + ".join(sorted(self.effects))
        return f"{ings} = {fx}"
    
    def __repr__(self):
        return " + ".join(sorted(self.ingredients.keys()))

    def add_ingredient(self, ingredient: Ingredient):
        self.ingredients[ingredient.key] = ingredient
        return self

    def remove_ingredient(self, ingredient: Ingredient):
        self.ingredients.pop(ingredient.key)
        return self

    def clear(self):
        self.sanitize()
        self.ingredients.clear()
    
    def sanitize(self):
        self._mixed = False
        self._checked = None
        self._ing_key = None
        self._fx_key = None
        self._weight = None
        self._value = None
        self.effects.clear()
        return self
    
    @property
    def effects_key(self) -> frozenset[str]:
        if self._fx_key is None and self._mixed:
            self._fx_key = frozenset(self.effects)
        return self._fx_key
    
    @property
    def ingredients_key(self) -> frozenset[str]:
        if self._ing_key is None:
            self._ing_key = frozenset(self.ingredients.keys())
        return self._ing_key
    
    @staticmethod
    def multi_intersect(set_list: List[Set]) -> Set:
        return reduce(lambda x,y: x | y, (c[0] & c[1] for c in combinations(set_list,2)), set())
    
    @property
    def mixed(self) -> bool:
        return self._mixed
    
    @property
    def checked(self) -> bool|None:
        return self._checked
    
    def mix(self):
        if len(self.ingredients) >= 2:
            ingvals = self.ingredients.values()
            fxlist = [ing.effects for ing in ingvals]
            self.effects = self.multi_intersect(fxlist)
            self._mixed = True
            self._checked = None
        return self
    
    @property
    def value(self) -> float:
        if self.mixed and self._value is None:
            self._value = sum([i.value for i in self.ingredients.values()])
        return self._value
    
    @property
    def weight(self) -> int:
        if self.mixed and self._weight is None:
            self._weight = reduce(lambda x,y: x + y, [i.weight for i in self.ingredients.values()], 0.0)
        return self._weight
    
    def check(self) -> bool:
        if not self._mixed:
            return False
        
        # only do this once since it can be computationally expensive
        if self._checked is None:
            if len(self.effects) == 0:
                # not matches
                self._checked = False
            elif len(self.ingredients) == 2:
                # if there are matches and only 2 ingredients, it's good
                self._checked = True
            elif len(self.effects) == 1 and len(self.ingredients) > 2:
                # a potion with only one effect and more than 2 ingredients is incomplete/excess
                self._checked = False
            else:
                # if there are excess ingredients, do not consider this a valid potion
                self._checked = not self.has_excess()
        
        return self._checked
    
    def has_excess(self) -> bool:
        # redundancy checks. this is exponentially slower as ingredients are added
        # elder scrolls is limited to 4 ingredients in oblivion/morrowind
        combosize = len(self.ingredients) - 1
        if combosize > 1:
            for combo in combinations(self.ingredients.values(), combosize):
                fxlist = [ing.effects for ing in combo]
                if self.multi_intersect(fxlist) == self.effects:
                    return True
        return False
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Potion):
            return False
        return self.ingredients_key == other.ingredients_key
    
    def summary(self) -> str:
        if not self._mixed:
            return None
        ings = ", ".join(self.ingredients.keys())
        fx = ", ".join(self.effects)
        return f"Ingredients: {ings}\nEffects:     {fx}\n"
    
    def print_recipe(self, head_chr: str = "=", width: int = 35, foot_chr: str = "=") -> int:
        ings = sorted(self.ingredients_key)
        ing_text = ""
        for i in ings:
            center_width = max(width - 2, len(i))
            ing_text += f"|{i.center(center_width)}|"
        
        if len(ing_text) == 0:
            return
            
        if head_chr is not None and len(head_chr) > 0:
            print(head_chr[:1] * len(ing_text))
        print(ing_text)
        if foot_chr is not None and len(foot_chr) > 0:
            print(foot_chr[:1] * len(ing_text))
            
        return len(ing_text)
    
    def print_potion(self):
        if not self._mixed:
            return
        
        ingredients = " + ".join(sorted(self.ingredients_key))
        effects = " + ".join(sorted(self.effects))
        
        twidth = max(len(ingredients), len(effects)) + 4
        print(f" {'=' * (twidth - 2)} ")
        print(f"|{ingredients.center(twidth - 2)}|")
        print(f"|{'#' * (twidth - 2)}|")
        print(f"|{effects.center(twidth - 2)}|")
        print(f" {'*' * (twidth - 2)} ")
    
    def enum_subsets(self, imin, imax) -> Iterator[tuple[Ingredient]]:
        for i in range(imin, imax):
            for combo in combinations(self.ingredients.values(), i):
                yield combo


class Laboratory:
    context: set[str]
    all_items: list[str]
    associated: Callable[[set|frozenset], set[str]]
    _pivot: Callable[[Optional[set]], object]
    
    def __init__(self, all_items: Iterable, context: Iterable|None = None):
        context = context or []
        self.context = set(context)
        self.all_items = sorted(all_items)
        self.associated = lambda x: set()
        self._pivot = lambda x: None
    
    def print_tabbed(self, items: Iterable[str], columns: int = 4, cwidth: int = 30):
        i = 0
        for item in items:
            if i % columns == 0 and i > 0:
                print('')
            s = f"{i}) {item}"
            print(f"{s.ljust(cwidth)}", end='')
            i += 1
        print('')
    
    def available(self) -> list[str]:
        if len(self.context) > 0:
            return sorted(self.associated(self.context))
        else:
            return self.all_items

    @property
    def stat(self):
        print("Selected:")
        print(self.context)
        print("Available:")
        print(self.available())
    
    @property
    def sanitize(self):
        self.context.clear()
        return self
    
    def add(self, item: str|int):
        available = self.available()
        if isinstance(item, int):
            if item >= 0 and item < len(available):
                self.context.add(available[item])
        elif isinstance(item, str):
            if item.strip() in available:
                self.context.add(item)
        return self
    
    def remove(self, item: str|int):
        available = sorted(self.context)
        if isinstance(item, int):
            if item >= 0 and item < len(available):
                self.context.remove(available[item])
        elif isinstance(item, str):
            if item.strip() in available:
                self.context.remove(item)
        return self
    
    @property
    def recipes(self):
        print("Not supported")
        
    def pivot(self) -> Self:
        print("Not supported")

    def info(self, item: str|int|None = None):
        print("Not supported")


class IngredientsLab(Laboratory):
    potion: Callable[[frozenset], Potion]
    ingredient: Callable[[str], Ingredient|None]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.potion = lambda x: None
        self.ingredient = lambda x: None
        
    @property
    def stat(self):
        available = self.available()
        selected = sorted(self.context)
        
        if len(selected) > 0:
            print("Selected:")
            self.print_tabbed(selected)
            k = frozenset(self.context)
            pot = self.potion(k)
            if pot is not None:
                print("\nEffects:")
                fx = sorted(pot.effects)
                self.print_tabbed(fx)
            else:
                print("\nNo Effects. Select more ingredients.")
            print("")
        
        if len(available) > 0:
            print("Available ingredients:")
            self.print_tabbed(available)

    def pivot(self) -> Laboratory:
        k = frozenset(self.context)
        pot = self.potion(k)
        if pot is not None:
            return self._pivot(pot.effects)
        return self._pivot()

    def print_ingredient(self, ingredient: Ingredient|None):
        if isinstance(ingredient, Ingredient):
            print(f"      Name: {ingredient.name}")
            print(f"    Source: {ingredient.source}")
            print(f"     Value: {ingredient.value}")
            print(f"    Weight: {ingredient.weight}")
            print(f"   Primary: {ingredient.primary}")
            print(f" Secondary: {ingredient.secondary}")
            print(f"  Tertiary: {ingredient.tertiary}")
            print(f"Quaternary: {ingredient.quaternary}")
        
    def info(self, ingredient: str|int|None = None):
        if isinstance(ingredient, int):
            if ingredient >= 0 and ingredient < len(self.all_items):
                self.print_ingredient(self.ingredient(self.all_items[ingredient]))
        elif isinstance(ingredient, str):
            self.print_ingredient(self.ingredient(ingredient.strip()))
        else:
            print("All ingredients:")
            self.print_tabbed(self.all_items)
            return
 
        
class EffectsLab(Laboratory):
    get_potions: Callable[[frozenset, Optional[Any]], Optional[list[Potion]]]
    ingredients: Callable[[str], set[str]]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_potions = lambda x,y: y
        self.ingredients = lambda x: set()
        
    @property
    def stat(self):
        available = self.available()
        selected = sorted(self.context)
        if len(selected) > 0:
            print(f"Selected effects:")
            self.print_tabbed(selected)
        
            pots = self.get_potions(frozenset(self.context), list())
            print(f"\nAvailable Recipes: {len(pots)}")
            print("")
        
        print("Available effects:")
        self.print_tabbed(available)
        print("")
        
    @property
    def recipes(self):
        selected = sorted(self.context)
        if len(selected) == 0:
            return
        print(f"Selected effects:")
        self.print_tabbed(selected)
        pots = self.get_potions(frozenset(self.context), list())
        pot_list = list()
        for pot in pots:
            pot_list.append(" + ".join(sorted(pot.ingredients_key)))
        pot_list.sort()
        radjust = len(str(len(pot_list)))
        print("\nAvailable Recipes:")
        for i in range(0, len(pot_list)):
            print(f"{str(i).rjust(radjust)}) {pot_list[i]}")
    
    def pivot(self, index: int = 0) -> Laboratory:
        pots = self.get_potions(frozenset(self.context), list())
        if index >= len(pots) or index < 0:
            return self._pivot()
        pot_list = list()
        ctx = None
        for pot in pots:
            pot_list.append(" + ".join(sorted(pot.ingredients_key)))
        pot_list.sort()
        for pot in pots:
            i = pot_list.index(" + ".join(sorted(pot.ingredients_key)))
            if i == index:
                ctx = pot.ingredients_key
                break
        return self._pivot(ctx)

    def info(self, effect: str|int|None = None):
        if isinstance(effect, int):
            print(f"Ingredients with {self.all_items[effect]}")
            self.print_tabbed(self.ingredients(self.all_items[effect]))
        elif isinstance(effect, str):
            print(f"Ingredients with {effect.strip()}")
            self.print_tabbed(self.ingredients(effect.strip()))
        else:
            print("All Effects:")
            self.print_tabbed(self.all_items)
            return


class Alchemist:
    recipes: dict[frozenset[str], Potion]
    potions: dict[frozenset[str], list[Potion]]
    researched: set[frozenset[str]]
    ingredients: IngredientCollection
    effects: dict[str, Effect]
    _max_ingredients: int
    
    def ilab(self, context: set|None = None) -> IngredientsLab:
        lab = IngredientsLab(self.ingredients.ingredient_map.keys(), context=context)
        lab.associated = self.associated_ingredients
        lab.potion = self.potion
        lab.ingredient = self.ingredient
        lab._pivot = self.elab
        return lab
    
    def elab(self, context: set|None = None) -> EffectsLab:
        lab = EffectsLab(self.ingredients.effect_map.keys(), context=context)
        lab.associated = self.associated_effects
        lab.get_potions = self.potions.get
        lab.ingredients = self.ingredients.with_effect
        lab._pivot = self.ilab
        return lab
    
    @classmethod
    def from_csv(cls,
                 ingredient_csv: str,
                 max_ingredients: int = 3,
                 negative_effects: Iterable[str]|None = None):
        alchemist = cls(ingredients=IngredientCollection.from_csv(file=ingredient_csv),
                        max_ingredients=max_ingredients)
        if negative_effects is not None:
            alchemist.set_effect_status(negative_effects, -1)
            alchemist.set_effect_status(negative_effects, 1, True)
        return alchemist
    
    @classmethod
    def from_jxz(cls, jxz_file: str, max_ingredients: int|None = None, load_potions: bool = True, load_recipes: bool = True):
        with lzma.open(jxz_file, 'rt') as jsonfile:
            j: dict = json.load(jsonfile)

        max_ingredients = max_ingredients or j.get('max_ingredients', None)
        if not isinstance(max_ingredients, int):
            raise TypeError(f"Invalid max ingredients: {str(max_ingredients)}. Must be integer.")
        
        ingredients = IngredientCollection(Ingredient.from_dict(d) for d in j.get('ingredients', []))
        
        effects: dict[str,Effect] = dict()
        fx: list[dict] = j.get('effects', [])
        for e in fx:
            f = Effect.from_dict(e)
            effects[f.name] = f
        
        al = cls(ingredients=ingredients, effects=effects, max_ingredients=max_ingredients)
        
        potions: list[list] = j.get('potions', None)
        recipes: list[list] = j.get('recipes', None)
        
        if recipes is not None and load_recipes:
            for r in recipes:
                s = frozenset(r)
                p = Potion(ingredients.lookup(i) for i in s)
                al.add_potion(p.mix())
        elif potions is not None and load_potions:
            # creating potions from recipes will make loading the potions section redundant
            # the potion path is made available for oblivion. because there are millions of unique recipes,
            #   potions are much faster to load, and then individual recipes can be calculated as needed
            for p in potions:
                s = frozenset(p)
                al.potions.setdefault(s, list())
        
        return al
    
    @property
    def max_ingredients(self) -> int:
        return self._max_ingredients
    
    def __init__(self,
                 ingredients: IngredientCollection,
                 effects: dict[str,Effect]|None = None,
                 max_ingredients: int = 3):
        self.ingredients = ingredients
        self.recipes = dict()
        self.potions = dict()
        self.researched = set()
        self._max_ingredients = max(max_ingredients, 2)
        
        self.effects = effects or dict()
        for effect in self.ingredients.effects():
            if effect not in self.effects:
                self.effects[effect] = Effect(name=effect)
    
    def set_effect_status(self, effects: Iterable[str], status: int, inverted: bool = False):
        setfx = set(effects)
        for effect in self.effects:
            if (effect in setfx) ^ (inverted):
                self.effects[effect].status = status
    
    def add_potion(self, potion: Potion):
        if potion.ingredients_key not in self.recipes:
            self.recipes[potion.ingredients_key] = potion
            self.potions.setdefault(potion.effects_key, list()).append(potion)
    
    def catalog_potions(self, mastery: Mastery = Mastery.EXPERT):
        self.recipes.clear()
        self.potions.clear()
        
        self.ingredients.mastery = mastery
        for combosize in range(2, self._max_ingredients + 1):
            for ings in combinations(self.ingredients.collection, combosize):
                potion = Potion.from_ingredients(ings)
                if potion is not None:
                    self.add_potion(potion)
        return self
    
    def ingredient(self, name: str) -> Ingredient:
        """Get ingredient by name

        Args:
            name (str): ingredient name

        Returns:
            Ingredient: ingredient that has been cataloged, or None
        """
        return self.ingredients.lookup(name)
        
    def potions_with_effects(self, effects: Iterable) -> dict[frozenset, list[Potion]]:
        """Gets a list of valid potions with passed effects

        Args:
            effects (set): set of effects that can appear in a potion

        Returns:
            dict: potions (inclusive) containing effect
        """
        pots = dict()
        fx = set(effects)
        uniquekeys = list(self.potions.keys())
        for k in filter(lambda x: fx.issubset(x), uniquekeys):
            pots[k] = self.potions[k]
        return pots

    def associated_effects(self, effects: set|frozenset) -> set[str]:
        """Gets other effects that can appear in valid potions with passed effects

        Args:
            effects (set|frozenset): set of effects that can appear in a potion

        Returns:
            set: set of other possible effects
        """
        # returns a sorted list of other possible effects with the given effects
        associated = set()
        for k in self.potions.keys():
            if effects.issubset(k):
                associated.update(k)
        return associated - effects

    def potions_with_ingredients(self, ingredient_names: Iterable) -> list[Potion]:
        """Get all potions containing (inclusive) ingredients

        Args:
            ingredient (Ingredient): Ingredients to query for

        Returns:
            list[Potion]: list of potions containing specified ingredients
        """
        pots = list()
        ings = set(ingredient_names)
        for p in self.recipes.keys():
            if ings.issubset(p):
                pots.append(self.recipes[p])
        return pots
    
    def associated_ingredients(self, ingredient_names: set|frozenset) -> set[str]:
        """Gets other ingredients that can appear in valid recipes with passed effects

        Args:
            ingredient_names (set|frozenset): set of ingredient names that can appear in a recipe

        Returns:
            set: set of other possible ingredients
        """
        ret = set()
        for p in self.recipes.keys():
            if ingredient_names.issubset(p):
                ret.update(p)
        return ret - ingredient_names
    
    def potion(self, recipe: Iterable[str]) -> Potion:
        """Potion by effects

        Args:
            recipe (frozenset): set of effects to query

        Returns:
            Potion: The potion with exact ingredients or None if it wasn't discovered
        """
        return self.recipes.get(frozenset(recipe))

    def research_recipes(self, potion_effects: frozenset[str]) -> List[frozenset[str]]:
        if potion_effects not in self.researched:
            test_ingredients = set()
            for e in potion_effects:
                test_ingredients.update(self.ingredients.effect_map.get(e, {}))
                    
            ubound = min(self._max_ingredients, len(test_ingredients)) + 1
            
            for combosize in range(2, ubound):
                for ings in combinations(test_ingredients, combosize):
                    potion = Potion([self.ingredients.lookup(i) for i in ings])
                    if potion.ingredients_key in self.recipes:
                        continue
                    if potion.mix().check():
                        self.add_potion(potion=potion)
        self.researched.add(potion_effects)
        return self.get_recipes(potion_effects=potion_effects)
    
    def get_recipes(self, potion_effects: frozenset[str]) -> List[frozenset[str]]:
        return [potion.ingredients_key for potion in self.potions.get(potion_effects, list())]
    
    def save_jxz(self, jxz_file: str, potions: bool = False, recipes: bool = False):
        outd = {"version":"1.0", "max_ingredients": self._max_ingredients}
        
        outd['ingredients'] = list()
        for ing in self.ingredients.collection:
            outd['ingredients'].append(ing.to_dict())
        
        outd['effects'] = list()
        for ef in self.effects.values():
            outd['effects'].append(ef.to_dict())
        
        if potions:
            outd['potions'] = list()
            for k in self.potions.keys():
                outd['potions'].append(sorted(k))
        
        if recipes:
            outd['recipes'] = list()
            for k in self.recipes.keys():
                outd['recipes'].append(sorted(k))
                
        with lzma.open(filename=jxz_file, mode='wt') as f:
            json.dump(outd, fp=f, indent=1)

    def print_recipes(self, effects: set):
        k = frozenset(effects)
        pots = self.potions.get(k, list())
        
        if len(pots) == 0:
            return
        
        selected = " + ".join(sorted(effects))
        longest = len(selected)
        
        recipe_list: list[str] = list()
        
        for pot in pots:
            recipe = " + ".join(sorted(pot.ingredients_key))
            longest = max(longest, len(recipe))
            recipe_list.append(recipe)

        twidth = longest + 2
        print(f" {'=' * twidth} ")
        print(f"|{selected.center(twidth)}|")
        print(f"|{'#' * twidth}|")
        
        recipe_list.sort()
        lastitem = recipe_list.pop(-1)
        for recipe in recipe_list:
            print(f"|{recipe.center(twidth)}|")
            print(f"|{'*' * twidth}|")
        print(f"|{lastitem.center(twidth)}|")
        print(f" {'*' * twidth} ")


class Oblivion(Alchemist):
    MAX_INGREDIENTS: int = 4
    DEFAULT_CSV: str = 'data/ESIV.csv'
    DEFAULT_FULL_JXZ: str = 'data/cache/ESIV.full.jxz'
    DEFAULT_LITE_JXZ: str = 'data/cache/ESIV.lite.jxz'
    NEGATIVE_EFFECTS: frozenset = frozenset((
        'Burden',
        'Damage Agility',
        'Damage Endurance',
        'Damage Fatigue',
        'Damage Health',
        'Damage Intelligence',
        'Damage Luck',
        'Damage Magicka',
        'Damage Personality',
        'Damage Speed',
        'Damage Strength',
        'Damage Willpower',
        'Drain Fatigue',
        'Drain Health',
        'Drain Intelligence',
        'Drain Magicka',
        'Fire Damage',
        'Frost Damage',
        'Paralyze',
        'Shock Damage',
        'Silence',
        'Weakness to Fire',
    ))
    
    @classmethod
    def create(cls, full=True):
        jxz_path = Path(cls.DEFAULT_FULL_JXZ)
        if jxz_path.exists() and full:
            print("WARNING: loading the full oblivion data set can be slow and uses a LOT of memory!")
            print("Loading from a jxz is faster than creating, but it will still be noticable.")
        if not jxz_path.exists() and not full:
            # can load lite from full, but if full doesn't exist try the lite archive
            jxz_path = Path(cls.DEFAULT_LITE_JXZ)
            
        if jxz_path.exists():
            return cls.from_jxz(jxz_file=str(jxz_path), load_potions=True, load_recipes=full)

        print("WARNING: creating oblivion alchemists from csv files can be VERY slow and uses a LOT of memory!")
        csv_path = Path(cls.DEFAULT_CSV)
        if csv_path.exists():
            alchemist = cls.from_csv(ingredient_csv=str(csv_path),
                                     max_ingredients=cls.MAX_INGREDIENTS,
                                     negative_effects=cls.NEGATIVE_EFFECTS)
            alchemist.catalog_potions()
            jxz_path.parent.mkdir(parents=True, exist_ok=True)
            alchemist.save_jxz(jxz_file=str(jxz_path), potions=True, recipes=full)
            return alchemist

        raise Exception("No data files found to create alchemist instance.")


class Skyrim(Alchemist):
    MAX_INGREDIENTS = 3
    DEFAULT_CSV = 'data/ESV.csv'
    DEFAULT_FULL_JXZ = 'data/cache/ESV.full.jxz'
    NEGATIVE_EFFECTS = frozenset((
        "Damage Health",
        "Damage Magicka",
        "Damage Magicka Regen",
        "Damage Stamina",
        "Damage Stamina Regen",
        "Fear",
        "Frenzy",
        "Lingering Damage Health",
        "Lingering Damage Magicka",
        "Lingering Damage Stamina",
        "Paralysis",
        "Ravage Health",
        "Ravage Magicka",
        "Ravage Stamina",
        "Slow",
        "Weakness to Fire",
        "Weakness to Frost",
        "Weakness to Magic",
        "Weakness to Poison",
        "Weakness to Shock",
    ))
    
    @classmethod
    def create(cls):
        jxz_path = Path(cls.DEFAULT_FULL_JXZ)
        if jxz_path.exists():
            return cls.from_jxz(jxz_file=str(jxz_path), load_potions=True, load_recipes=True)
            
        csv_path = Path(cls.DEFAULT_CSV)
        if csv_path.exists():
            alchemist = cls.from_csv(ingredient_csv=str(csv_path),
                                     max_ingredients=cls.MAX_INGREDIENTS,
                                     negative_effects=cls.NEGATIVE_EFFECTS)
            alchemist.catalog_potions()
            jxz_path.parent.mkdir(parents=True, exist_ok=True)
            alchemist.save_jxz(jxz_file=str(jxz_path), potions=True, recipes=True)
            return alchemist

        raise Exception("No data files found to create alchemist instance.")
