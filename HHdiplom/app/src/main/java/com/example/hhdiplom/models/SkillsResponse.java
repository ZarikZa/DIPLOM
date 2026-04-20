package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

import java.util.List;

public class SkillsResponse {
    @SerializedName("results")
    private List<SkillItem> results;

    public List<SkillItem> getResults() { return results; }
}
