package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class CompanyProfile {
    @SerializedName("id")
    private int id;

    @SerializedName("name")
    private String name;

    @SerializedName("number")
    private String number;

    @SerializedName("industry")
    private String industry;

    @SerializedName("description")
    private String description;

    @SerializedName("status")
    private String status;

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

    public String getNumber() {
        return number;
    }

    public void setNumber(String number) {
        this.number = number;
    }

    public String getIndustry() {
        return industry;
    }

    public void setIndustry(String industry) {
        this.industry = industry;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
