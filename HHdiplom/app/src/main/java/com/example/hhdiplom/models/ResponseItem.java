package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ResponseItem {
    @SerializedName("id")
    private int id;

    @SerializedName("applicant_name")
    private String applicantName;

    @SerializedName("vacancy_position")
    private String vacancyPosition;

    @SerializedName("company_name")
    private String companyName;

    @SerializedName("status_name")
    private String statusName;

    @SerializedName("response_date")
    private String responseDate;

    @SerializedName("applicants")
    private int applicantId;

    @SerializedName("vacancy_id")
    private int vacancyId;

    @SerializedName("status")
    private int statusId;

    // Геттеры
    public int getId() {
        return id;
    }

    public String getApplicantName() {
        return applicantName;
    }

    public String getVacancyPosition() {
        return vacancyPosition;
    }

    public String getCompanyName() {
        return companyName;
    }

    public String getStatusName() {
        return statusName;
    }

    public String getResponseDate() {
        return responseDate;
    }

    public int getApplicantId() {
        return applicantId;
    }

    public int getVacancyId() {
        return vacancyId;
    }

    public int getStatusId() {
        return statusId;
    }
}