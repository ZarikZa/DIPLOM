package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Complaint {
    @SerializedName("id")
    private int id;

    @SerializedName("vacancy")
    private int vacancyId;

    @SerializedName("complainant")
    private int complainantId;

    @SerializedName("complaint_type")
    private String complaintType; // spam, fraud и т.д.

    @SerializedName("description")
    private String description;

    @SerializedName("status")
    private String status; // pending, reviewed и т.д.

    @SerializedName("created_at")
    private String createdAt;

    @SerializedName("resolved_at")
    private String resolvedAt;

    @SerializedName("admin_notes")
    private String adminNotes;

    // Геттеры и сеттеры
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getVacancyId() { return vacancyId; }
    public void setVacancyId(int vacancyId) { this.vacancyId = vacancyId; }

    public int getComplainantId() { return complainantId; }
    public void setComplainantId(int complainantId) { this.complainantId = complainantId; }

    public String getComplaintType() { return complaintType; }
    public void setComplaintType(String complaintType) { this.complaintType = complaintType; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }

    public String getResolvedAt() { return resolvedAt; }
    public void setResolvedAt(String resolvedAt) { this.resolvedAt = resolvedAt; }

    public String getAdminNotes() { return adminNotes; }
    public void setAdminNotes(String adminNotes) { this.adminNotes = adminNotes; }
}