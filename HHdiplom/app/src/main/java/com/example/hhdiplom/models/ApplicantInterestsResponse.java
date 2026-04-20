package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

import java.util.ArrayList;
import java.util.List;

public class ApplicantInterestsResponse {
    @SerializedName("categories")
    private List<String> categories;

    @SerializedName("available_categories")
    private List<String> availableCategories;

    public List<String> getCategories() {
        return categories != null ? categories : new ArrayList<>();
    }

    public List<String> getAvailableCategories() {
        return availableCategories != null ? availableCategories : new ArrayList<>();
    }
}
