package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;
import java.util.List;

public class ResponsesResponse {
    @SerializedName("count")
    private int count;

    @SerializedName("next")
    private String next;

    @SerializedName("previous")
    private String previous;

    @SerializedName("results")
    private List<ResponseItem> results;

    // Геттеры
    public int getCount() {
        return count;
    }

    public String getNext() {
        return next;
    }

    public String getPrevious() {
        return previous;
    }

    public List<ResponseItem> getResults() {
        return results;
    }
}