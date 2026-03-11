import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';

import { useAuth } from '../app/auth';

type TranslationValues = Record<string, string | number | boolean | null | undefined>;
type TranslationMap = Record<string, string>;
export type LanguageMeta = {
  code: string;
  native_label: string;
  flag: string;
  default_timezone: string;
  timezones: string[];
};

type LocaleFile = {
  _meta: LanguageMeta;
  strings: TranslationMap;
};

const DEFAULT_LANGUAGE = 'en';

function readString(value: unknown, field: string, source: string): string {
  if (typeof value !== 'string') {
    throw new Error(`invalid locale ${source}: '${field}' must be a string`);
  }
  const text = value.trim();
  if (!text) {
    throw new Error(`invalid locale ${source}: '${field}' must not be empty`);
  }
  return text;
}

function readStringArray(value: unknown, field: string, source: string): string[] {
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error(`invalid locale ${source}: '${field}' must be a non-empty array of strings`);
  }
  const items = value.map((entry, index) => readString(entry, `${field}[${index}]`, source));
  const deduplicated = [...new Set(items)];
  if (deduplicated.length !== items.length) {
    throw new Error(`invalid locale ${source}: '${field}' must not contain duplicates`);
  }
  return deduplicated;
}

function loadLocales(): { dictionaries: Record<string, TranslationMap>; languages: LanguageMeta[] } {
  const localeModules = import.meta.glob('./locales/*/common.json', { eager: true }) as Record<string, { default: LocaleFile }>;
  const dictionaries: Record<string, TranslationMap> = {};
  const languages: LanguageMeta[] = [];

  for (const [path, module] of Object.entries(localeModules)) {
    const payload = module.default;
    if (!payload || typeof payload !== 'object') {
      throw new Error(`invalid locale file '${path}': expected object`);
    }
    if (!payload._meta || typeof payload._meta !== 'object') {
      throw new Error(`invalid locale file '${path}': missing '_meta' object`);
    }
    if (!payload.strings || typeof payload.strings !== 'object' || Array.isArray(payload.strings)) {
      throw new Error(`invalid locale file '${path}': missing 'strings' object`);
    }

    const language: LanguageMeta = {
      code: readString(payload._meta.code, 'code', path),
      native_label: readString(payload._meta.native_label, 'native_label', path),
      flag: readString(payload._meta.flag, 'flag', path),
      default_timezone: readString(payload._meta.default_timezone, 'default_timezone', path),
      timezones: readStringArray(payload._meta.timezones, 'timezones', path),
    };
    if (!language.timezones.includes(language.default_timezone)) {
      throw new Error(`invalid locale ${path}: 'default_timezone' must be listed in '_meta.timezones'`);
    }
    if (dictionaries[language.code]) {
      throw new Error(`duplicate locale code '${language.code}' in '${path}'`);
    }

    const strings: TranslationMap = {};
    for (const [key, value] of Object.entries(payload.strings)) {
      if (typeof value !== 'string') {
        throw new Error(`invalid locale ${path}: key '${key}' must map to a string`);
      }
      strings[key] = value;
    }

    dictionaries[language.code] = strings;
    languages.push(language);
  }

  if (!dictionaries[DEFAULT_LANGUAGE]) {
    throw new Error(`missing default locale '${DEFAULT_LANGUAGE}'`);
  }

  languages.sort((a, b) => {
    if (a.code === DEFAULT_LANGUAGE) return -1;
    if (b.code === DEFAULT_LANGUAGE) return 1;
    return a.code.localeCompare(b.code);
  });

  return { dictionaries, languages };
}

const { dictionaries, languages } = loadLocales();
const defaultDictionary = dictionaries[DEFAULT_LANGUAGE];

interface I18nContextValue {
  language: string;
  timezone: string;
  languages: LanguageMeta[];
  t: (key: string, values?: TranslationValues) => string;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

function interpolate(template: string, values?: TranslationValues): string {
  if (!values) return template;
  return template.replace(/\{([A-Za-z0-9_]+)\}/g, (_, token: string) => {
    const value = values[token];
    return value === undefined || value === null ? '' : String(value);
  });
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  const requestedLanguage = String(user?.language || DEFAULT_LANGUAGE);
  const language = requestedLanguage in dictionaries ? requestedLanguage : DEFAULT_LANGUAGE;
  const timezone = String(user?.timezone || '').trim();
  const dictionary = dictionaries[language];

  const t = useCallback(
    (key: string, values?: TranslationValues) => {
      const text = dictionary[key] ?? defaultDictionary[key] ?? '';
      return interpolate(text, values);
    },
    [dictionary]
  );

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      timezone,
      languages,
      t,
    }),
    [language, timezone, t]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider');
  }
  return context;
}
