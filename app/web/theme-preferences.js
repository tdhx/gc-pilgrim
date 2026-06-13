export const THEME_STORAGE_KEY = "gc-pilgrim-theme";
export const LITURGICAL_DETAIL_STORAGE_KEY = "gc-pilgrim-liturgical-detail";
export const OBSOLETE_APPEARANCE_STORAGE_KEY = "gc-pilgrim-appearance";
export const MASCOT_STORAGE_KEY = "gc-pilgrim-mascot";

export const THEME_CHOICES = ["parish", "pilgrim", "traditional"];
export const LITURGICAL_DETAIL_CHOICES = ["simple", "rich"];
export const MASCOT_CHOICES = ["boy", "girl"];

export function validThemeChoice(value) {
  return THEME_CHOICES.includes(value) ? value : "parish";
}

export function validLiturgicalDetail(value) {
  return LITURGICAL_DETAIL_CHOICES.includes(value) ? value : "rich";
}

export function validMascot(value) {
  return MASCOT_CHOICES.includes(value) ? value : "boy";
}

export function mascotAsset(value) {
  return validMascot(value) === "girl"
    ? "assets/gold-coast-mascot-girl.png"
    : "assets/gold-coast-mascot.png";
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
    mascot: validMascot(storage?.getItem(MASCOT_STORAGE_KEY)),
  };
}

export function savePreferences(storage, preferences) {
  storage?.setItem(THEME_STORAGE_KEY, validThemeChoice(preferences.theme));
  storage?.setItem(
    LITURGICAL_DETAIL_STORAGE_KEY,
    validLiturgicalDetail(preferences.liturgicalDetail),
  );
  storage?.setItem(MASCOT_STORAGE_KEY, validMascot(preferences.mascot));
}

export function showRichLiturgicalInformation(detail) {
  return validLiturgicalDetail(detail) === "rich";
}
