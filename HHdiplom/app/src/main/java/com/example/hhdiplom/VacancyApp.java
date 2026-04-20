package com.example.hhdiplom;

import android.app.Application;

import com.example.hhdiplom.utils.LanguagePrefs;
import com.example.hhdiplom.utils.ThemePrefs;

public class VacancyApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        ThemePrefs.applySavedTheme(this);
        LanguagePrefs.applySavedLanguage(this);
    }
}
