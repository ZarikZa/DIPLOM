package com.example.hhdiplom.utils;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.appcompat.app.AppCompatDelegate;
import androidx.core.os.LocaleListCompat;

public class LanguagePrefs {

    public static final String LANG_RU = "ru";
    public static final String LANG_EN = "en";

    private static final String PREFS = "app_prefs";
    private static final String KEY_LANGUAGE = "app_language";

    private LanguagePrefs() {
    }

    public static void applySavedLanguage(Context context) {
        String language = getSavedLanguage(context);
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(language));
    }

    public static String getSavedLanguage(Context context) {
        SharedPreferences sp = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return sp.getString(KEY_LANGUAGE, LANG_RU);
    }

    public static void setLanguage(Context context, String language) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_LANGUAGE, language)
                .apply();
        applySavedLanguage(context);
    }
}
