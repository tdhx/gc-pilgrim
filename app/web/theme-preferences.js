export const THEME_STORAGE_KEY = "gc-pilgrim-theme";
export const LITURGICAL_DETAIL_STORAGE_KEY = "gc-pilgrim-liturgical-detail";
export const OBSOLETE_APPEARANCE_STORAGE_KEY = "gc-pilgrim-appearance";

export const THEME_CHOICES = ["parish", "pilgrim", "traditional"];
export const LITURGICAL_DETAIL_CHOICES = ["simple", "rich"];

export function validThemeChoice(value) {
  return THEME_CHOICES.includes(value) ? value : "parish";
}

export function validLiturgicalDetail(value) {
  return LITURGICAL_DETAIL_CHOICES.includes(value) ? value : "rich";
}

export function resolvedTheme(choice, parishTheme = "gc-pilgrim") {
  const validChoice = validThemeChoice(choice);
  if (validChoice === "traditional") return "traditional";
  if (validChoice === "pilgrim") return "gc-pilgrim";
  return parishTheme || "gc-pilgrim";
}

export function readPreferences(storage) {
  storage?.removeItem?.(OBSOLETE_APPEARANCE_STORAGE_KEY);
  return {
    theme: validThemeChoice(storage?.getItem(THEME_STORAGE_KEY)),
    liturgicalDetail: validLiturgicalDetail(
      storage?.getItem(LITURGICAL_DETAIL_STORAGE_KEY),
    ),
  };
}

export function savePreferences(storage, preferences) {
  storage?.setItem(THEME_STORAGE_KEY, validThemeChoice(preferences.theme));
  storage?.setItem(
    LITURGICAL_DETAIL_STORAGE_KEY,
    validLiturgicalDetail(preferences.liturgicalDetail),
  );
}

export function showRichLiturgicalInformation(detail) {
  return validLiturgicalDetail(detail) === "rich";
}
