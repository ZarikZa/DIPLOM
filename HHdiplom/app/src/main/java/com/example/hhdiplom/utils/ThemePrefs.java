package com.example.hhdiplom.utils;

import android.content.Context;
import android.content.SharedPreferences;

import androidx.appcompat.app.AppCompatDelegate;

public class ThemePrefs {

    private static final String PREFS = "app_prefs";
    private static final String KEY_THEME = "theme_mode"; // 0=light, 1=dark

    public static void applySavedTheme(Context context) {
        int mode = getSavedTheme(context);
        AppCompatDelegate.setDefaultNightMode(mode == 1
                ? AppCompatDelegate.MODE_NIGHT_YES
                : AppCompatDelegate.MODE_NIGHT_NO);
    }

    public static int getSavedTheme(Context context) {
        SharedPreferences sp = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return sp.getInt(KEY_THEME, 0);
    }

    public static void toggleTheme(Context context) {
        int current = getSavedTheme(context);
        int next = (current == 1) ? 0 : 1;

        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putInt(KEY_THEME, next)
                .apply();

        AppCompatDelegate.setDefaultNightMode(next == 1
                ? AppCompatDelegate.MODE_NIGHT_YES
                : AppCompatDelegate.MODE_NIGHT_NO);
    }
}
