package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class RefreshTokenRequest {
    @SerializedName("refresh")
    private String refreshToken;

    public RefreshTokenRequest(String refreshToken) {
        this.refreshToken = refreshToken;
    }

    public String getRefreshToken() {
        return refreshToken;
    }

    public void setRefreshToken(String refreshToken) {
        this.refreshToken = refreshToken;
    }
}