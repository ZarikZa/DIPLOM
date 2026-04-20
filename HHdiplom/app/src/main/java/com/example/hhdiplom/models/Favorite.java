package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Favorite {
    @SerializedName("id")
    private int id;

    @SerializedName("applicant")
    private int applicantId;

    @SerializedName("vacancy")
    private int vacancyId;

    @SerializedName("added_date")
    private String addedDate;

    // Геттеры и сеттеры
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getApplicantId() { return applicantId; }
    public void setApplicantId(int applicantId) { this.applicantId = applicantId; }

    public int getVacancyId() { return vacancyId; }
    public void setVacancyId(int vacancyId) { this.vacancyId = vacancyId; }

    public String getAddedDate() { return addedDate; }
    public void setAddedDate(String addedDate) { this.addedDate = addedDate; }
}