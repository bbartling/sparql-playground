# Day 34 — The menu graph: which menu items depend on the fryer?

**Goal:** join three files into one graph and answer "what depends on what" questions with property paths.

## Read

[`burger_barn_menu.ttl`](burger_barn_menu.ttl) says what Burger Barn serves, what's in each item, and which
equipment cooks or stores each part. It uses the same names as `burger_barn.ttl` (`bb:Fryer_1`), so loading both
files into one graph joins them. No keys, no join columns: **the same IRI is the same thing**.

The menu has layers: a combo *includes* items, an item *has ingredients*, an ingredient is *cooked on* a fryer. A
property path follows all of them in one pattern:

```sparql
?item (bb:includes|bb:hasIngredient)*/bb:cookedOn ?fryer .
```

| Path piece | Means |
|---|---|
| `bb:includes|bb:hasIngredient` | either property |
| `( ... )*` | zero or more steps of it |
| `/bb:cookedOn` | then exactly one `cookedOn` step |

So it matches Fries (cooked on Fryer_1 directly), the chicken sandwich (has crispy chicken, cooked on Fryer_1) and
the Barn combo (includes fries). [`day34_rdf.py`](day34_rdf.py) asks three questions: which items need a fryer,
what comes off the menu if Fryer_2 breaks, and which items need the walk-in cooler.

## Run

```bash
uv run python lessons/course.py run 34
```

```
Menu items that need a fryer:
   BarnCombo needs Fryer_1
   ChickenSandwich needs Fryer_1
   Fries needs Fryer_1
   OnionRings needs Fryer_2
If Fryer_2 breaks, off the menu: ['OnionRings']
Items that need the walk-in cooler: ['BarnCombo', 'ChickenSandwich', 'ClassicBurger']
```

If Fryer_2 breaks, only the onion rings go. If the walk-in cooler fails, half the menu does. The Barn combo is in
both lists through a chain of three links, and nobody wrote "the combo needs the cooler" anywhere.

## How this maps to buildings

> **Buildings box.** Swap the words: "which zones lose cooling if chiller 1 trips?" is
> `?zone ^brick:feeds+ :Chiller_1`, the same "what depends on this" walk over **Brick**'s `brick:feeds`.
> **ASHRAE 223P** models the connections in even more detail (equipment, connection points and the connections
> between them), so the walk follows the actual pipes and ducts. FDD tools use exactly this to group alarms by
> their root cause.

## Why it matters

Dependency questions are where graphs beat tables. In SQL each layer is another self-join; here it's one `*`.

## Try it

1. What comes off the menu if the grill breaks?
2. Add a "Fish sandwich" with a "Fish fillet" ingredient cooked on Fryer_2. Re-run: what changes?
3. **Mini challenge (Burger Barn):** how many calories is the Barn combo? (Each item has `bb:hasCalories`; the
   combo doesn't.)

<details><summary>Answers</summary>

1. Swap `bb:Fryer_2` for `bb:Grill_1` in the "breaks" query: the classic burger and the Barn combo.
2. The fish sandwich appears with Fryer_2 in the first list and in "if Fryer_2 breaks".
3. **1010** (540 + 320 + 150):

   ```sparql
   SELECT (SUM(?calories) AS ?total) WHERE {
     bb:BarnCombo bb:includes ?item . ?item bb:hasCalories ?calories
   }
   ```

   (The course's tests check this answer.)

</details>
