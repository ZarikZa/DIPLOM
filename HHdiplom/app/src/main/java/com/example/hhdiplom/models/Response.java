package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Response {
    @SerializedName("id")
    private int id;

    @SerializedName("applicants")
    private int applicantId;

    @SerializedName("vacancy")
    private int vacancyId;

    @SerializedName("response_date")
    private String responseDate;

    @SerializedName("status")
    private int statusId; // Ссылка на StatusResponse

    // Геттеры и сеттеры
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getApplicantId() { return applicantId; }
    public void setApplicantId(int applicantId) { this.applicantId = applicantId; }

    public int getVacancyId() { return vacancyId; }
    public void setVacancyId(int vacancyId) { this.vacancyId = vacancyId; }

    public String getResponseDate() { return responseDate; }
    public void setResponseDate(String responseDate) { this.responseDate = responseDate; }

    public int getStatusId() { return statusId; }
    public void setStatusId(int statusId) { this.statusId = statusId; }

}