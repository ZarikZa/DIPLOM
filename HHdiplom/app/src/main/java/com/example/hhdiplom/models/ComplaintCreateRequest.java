package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ComplaintCreateRequest {

    @SerializedName("vacancy")
    private int vacancy;

    @SerializedName("complaint_type")
    private String complaintType; // spam, fraud, inappropriate, discrimination, false_info, other

    @SerializedName("description")
    private String description;

    public ComplaintCreateRequest(int vacancy, String complaintType, String description) {
        this.vacancy = vacancy;
        this.complaintType = complaintType;
        this.description = description;
    }

    public int getVacancy() { return vacancy; }
    public String getComplaintType() { return complaintType; }
    public String getDescription() { return description; }
}
