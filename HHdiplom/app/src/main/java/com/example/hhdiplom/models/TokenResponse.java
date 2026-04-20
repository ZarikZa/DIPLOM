package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class TokenResponse {
    @SerializedName("access")
    private String accessToken;

    @SerializedName("refresh")
    private String refreshToken;

    @SerializedName("user_id")
    private int userId;

    @SerializedName("username")
    private String username;

    @SerializedName("email")
    private String email;

    @SerializedName("user_type")
    private String userType;

    public String getAccessToken() { return accessToken; }
    public void setAccessToken(String accessToken) { this.accessToken = accessToken; }

    public String getRefreshToken() { return refreshToken; }
    public void setRefreshToken(String refreshToken) { this.refreshToken = refreshToken; }

    public int getUserId() { return userId; }
    public void setUserId(int userId) { this.userId = userId; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public String getUserType() { return userType; }
    public void setUserType(String userType) { this.userType = userType; }
}