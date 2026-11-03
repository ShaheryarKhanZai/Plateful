/** Decorative helpers. There are no photos in this demo, so each restaurant gets a
 *  colour theme and food emoji. Colours are dark enough for white text on top. */
const THEMES: [string, string][] = [
  ["#C2410C", "#9D174D"], ["#047857", "#0E5A7A"], ["#5B3FD1", "#2F4BB8"],
  ["#B45309", "#BE123C"], ["#1D6FC4", "#0F4C8A"], ["#BE185D", "#6D28D9"],
];
// Cuisine decides the colours when we know it (spice = orange, noodles = violet, ...),
// so neighbouring cards don't look alike. Unknown cuisines fall back to a name-based pick.
const CUISINE_THEME: [RegExp, number][] = [
  [/indian|curry/i, 0], [/healthy|salad|vegan/i, 1], [/asian|noodle|chinese|thai/i, 2],
  [/pizza|ital/i, 3], [/burger|american/i, 4], [/dessert|sweet/i, 5],
];

export function themeFor(name: string, cuisine = ""): { a: string; b: string; gradient: string; tint: string } {
  const byCuisine = CUISINE_THEME.find(([re]) => re.test(cuisine))?.[1];
  const i = byCuisine ?? [...name].reduce((n, c) => n + c.charCodeAt(0), 0) % THEMES.length;
  const [a, b] = THEMES[i];
  return { a, b, gradient: `linear-gradient(135deg, ${a}, ${b})`, tint: `${a}1F` };
}

const CUISINE: [RegExp, string][] = [
  [/indian|curry/i, "🍛"], [/asian|noodle|chinese|thai/i, "🍜"], [/pizza|ital/i, "🍕"],
  [/health|salad|vegan|bowl/i, "🥗"], [/burger|american/i, "🍔"], [/dessert|sweet|ice/i, "🍨"],
];
export const cuisineEmoji = (cuisine: string) => CUISINE.find(([re]) => re.test(cuisine))?.[1] ?? "🍽️";

const ITEMS: [RegExp, string][] = [
  [/wrap|roll up|shawarma/i, "🌯"], [/spring roll/i, "🥠"], [/dumpling|gyoza|momo/i, "🥟"],
  [/noodle|ramen|pasta/i, "🍜"], [/pizza|margherita|funghi|pepperoni/i, "🍕"],
  [/karahi|curry|biryani|lamb|masala/i, "🍛"], [/naan|bread|roti/i, "🍞"],
  [/salad|burrata|bowl/i, "🥗"], [/falafel/i, "🥙"], [/burger/i, "🍔"], [/fries/i, "🍟"],
  [/lassi|juice|smoothie|shake/i, "🥤"], [/tea|coffee/i, "☕"],
  [/kulfi|sorbet|ice cream|gelato|dessert|cake/i, "🍨"],
];
export const itemEmoji = (name: string, cuisine = "") =>
  ITEMS.find(([re]) => re.test(name))?.[1] ?? cuisineEmoji(cuisine);
