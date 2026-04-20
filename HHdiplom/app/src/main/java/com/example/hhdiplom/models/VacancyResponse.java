package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;
import java.util.List;

public class VacancyResponse {
    @SerializedName("count")
    private int count;

    @SerializedName("next")
    private String next;

    @SerializedName("previous")
    private String previous;

    @SerializedName("results")
    private List<Vacancy> results;

    // Геттеры и сеттеры
    public int getCount() {
        return count;
    }

    public void setCount(int count) {
        this.count = count;
    }

    public String getNext() {
        return next;
    }

    public void setNext(String next) {
        this.next = next;
    }

    public String getPrevious() {
        return previous;
    }

    public void setPrevious(String previous) {
        this.previous = previous;
    }

    public List<Vacancy> getResults() {
        return results;
    }

    public void setResults(List<Vacancy> results) {
        this.results = results;
    }
}