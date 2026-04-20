package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ApplicantSkillSuggestionCreateRequest {
    @SerializedName("name")
    private final String name;

    public ApplicantSkillSuggestionCreateRequest(String name) {
        this.name = name;
    }
}
