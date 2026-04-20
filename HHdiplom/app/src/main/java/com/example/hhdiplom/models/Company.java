package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Company {
    @SerializedName("id")
    private int id;

    @SerializedName("user")
    private int userId;

    @SerializedName("name")
    private String name;

    @SerializedName("number")
    private String number;

    @SerializedName("industry")
    private String industry;

    @SerializedName("description")
    private String description;

    @SerializedName("theme")
    private String theme;

    @SerializedName("status")
    private String status; // pending, approved, rejected

    @SerializedName("verification_document")
    private String verificationDocument;

    @SerializedName("created_at")
    private String createdAt;

    // Геттеры и сеттеры
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getUserId() { return userId; }
    public void setUserId(int userId) { this.userId = userId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getNumber() { return number; }
    public void setNumber(String number) { this.number = number; }

    public String getIndustry() { return industry; }
    public void setIndustry(String industry) { this.industry = industry; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getTheme() { return theme; }
    public void setTheme(String theme) { this.theme = theme; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getVerificationDocument() { return verificationDocument; }
    public void setVerificationDocument(String verificationDocument) { this.verificationDocument = verificationDocument; }

    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
}