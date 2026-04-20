package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class LikeResponse {

    @SerializedName("liked")
    private boolean liked;

    public boolean isLiked() {
        return liked;
    }

    public void setLiked(boolean liked) {
        this.liked = liked;
    }
}
