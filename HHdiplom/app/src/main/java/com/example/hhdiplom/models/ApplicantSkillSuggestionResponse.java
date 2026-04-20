package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ApplicantSkillSuggestionResponse {
    @SerializedName("id")
    private int id;

    @SerializedName("name")
    private String name;

    @SerializedName("status")
    private String status;

    public int getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getStatus() {
        return status;
    }
}
