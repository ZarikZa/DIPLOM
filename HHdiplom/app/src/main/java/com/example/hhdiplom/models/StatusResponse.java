package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class StatusResponse {
    @SerializedName("id")
    private int id;

    @SerializedName("status_response_name")
    private String name;

    // Геттеры и сеттеры
    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    @Override
    public String toString() {
        return name;
    }
}