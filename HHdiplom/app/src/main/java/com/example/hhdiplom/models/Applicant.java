package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Applicant {
    @SerializedName("id")
    private int id;

    @SerializedName("user")
    private int userId;

    @SerializedName("first_name")
    private String firstName;

    @SerializedName("last_name")
    private String lastName;

    @SerializedName("birth_date")
    private String birthDate; // YYYY-MM-DD

    @SerializedName("resume")
    private String resume;

    @SerializedName("theme")
    private String theme;

    // Геттеры и сеттеры
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getUserId() { return userId; }
    public void setUserId(int userId) { this.userId = userId; }

    public String getFirstName() { return firstName; }
    public void setFirstName(String firstName) { this.firstName = firstName; }

    public String getLastName() { return lastName; }
    public void setLastName(String lastName) { this.lastName = lastName; }

    public String getBirthDate() { return birthDate; }
    public void setBirthDate(String birthDate) { this.birthDate = birthDate; }

    public String getResume() { return resume; }
    public void setResume(String resume) { this.resume = resume; }

    public String getTheme() { return theme; }
    public void setTheme(String theme) { this.theme = theme; }
}