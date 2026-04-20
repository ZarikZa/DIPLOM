package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ToggleFavoriteResponse {
    @SerializedName("is_favorite")
    private boolean isFavorite;

    public boolean isFavorite() {
        return isFavorite;
    }
}
