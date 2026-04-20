package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

import java.util.List;

public class ApplicantInterestsUpdateRequest {
    @SerializedName("categories")
    private final List<String> categories;

    public ApplicantInterestsUpdateRequest(List<String> categories) {
        this.categories = categories;
    }
}
