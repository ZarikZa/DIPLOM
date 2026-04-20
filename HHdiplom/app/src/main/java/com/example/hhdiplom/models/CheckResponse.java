package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class CheckResponse {
    @SerializedName("has_responded")
    private boolean hasResponded;

    @SerializedName("response_id")
    private int responseId;

    @SerializedName("status")
    private String status;

    // Геттеры
    public boolean isHasResponded() {
        return hasResponded;
    }

    public int getResponseId() {
        return responseId;
    }

    public String getStatus() {
        return status;
    }
}