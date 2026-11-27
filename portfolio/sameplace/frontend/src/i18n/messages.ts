import ru from "./messages.ru.json";

export const DEFAULT_LOCALE = "ru" as const;
export type MessageKey = keyof typeof ru;
export type Dictionary = Readonly<Record<MessageKey, string>>;
export type MessageArgs = Readonly<Record<string, string | number>>;

const dictionaries = { ru } satisfies Record<string, Dictionary>;
export type Locale = keyof typeof dictionaries;
export const SUPPORTED_LOCALES = Object.freeze(Object.keys(dictionaries) as Locale[]);

type TranslationOptions = { strict?: boolean; dictionary?: Dictionary };

export function resolveLocale(requested: string | undefined): Locale {
  const language = requested?.trim().toLowerCase().split(/[-_]/)[0];
  return SUPPORTED_LOCALES.find((locale) => locale === language) ?? DEFAULT_LOCALE;
}

export function createTranslator(requested: string | undefined, options: TranslationOptions = {}) {
  const dictionary = options.dictionary ?? dictionaries[resolveLocale(requested)];
  const fail = (key: string): string => {
    if (options.strict) throw new Error(`Missing or invalid SamePlace message: ${key}`);
    return ru["fallback.missing"];
  };
  return (key: MessageKey, args: MessageArgs = {}): string => {
    if (!Object.prototype.hasOwnProperty.call(dictionary, key)) return fail(key);
    const template = dictionary[key];
    if (typeof template !== "string" || !template) return fail(key);
    let missing = false;
    const value = template.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g, (_match, name: string) => {
      if (!Object.prototype.hasOwnProperty.call(args, name)) {
        missing = true;
        return "";
      }
      return String(args[name]);
    });
    return missing ? fail(key) : value;
  };
}

export function playerCount(count: number, requested?: string): string {
  if (!Number.isSafeInteger(count) || count < 0) throw new RangeError("Invalid player count");
  const locale = resolveLocale(requested);
  const category = new Intl.PluralRules(locale).select(count);
  const key: MessageKey = category === "one" ? "players.one"
    : category === "few" ? "players.few"
    : category === "many" ? "players.many" : "players.other";
  return createTranslator(locale, { strict: true })(key, { count: new Intl.NumberFormat(locale).format(count) });
}
