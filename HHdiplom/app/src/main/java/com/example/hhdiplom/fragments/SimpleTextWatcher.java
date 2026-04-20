package com.example.hhdiplom.fragments;

import android.text.Editable;
import android.text.TextWatcher;

public class SimpleTextWatcher implements TextWatcher {

    public interface OnTextChangedListener {
        void onTextChanged(String text);
    }

    private final OnTextChangedListener listener;

    public SimpleTextWatcher(OnTextChangedListener listener) {
        this.listener = listener;
    }

    @Override
    public void beforeTextChanged(CharSequence s, int start, int count, int after) {
        // nothing
    }

    @Override
    public void onTextChanged(CharSequence s, int start, int before, int count) {
        // nothing
    }

    @Override
    public void afterTextChanged(Editable s) {
        if (listener != null) {
            listener.onTextChanged(s.toString());
        }
    }
}
