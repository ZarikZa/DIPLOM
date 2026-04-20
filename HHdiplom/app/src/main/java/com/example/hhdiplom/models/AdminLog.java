package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class AdminLog {
    @SerializedName("id")
    private int id;

    @SerializedName("admin")
    private int adminId;

    @SerializedName("action")
    private String action;

    @SerializedName("target_company")
    private Integer targetCompanyId;

    @SerializedName("target_object_id")
    private Integer targetObjectId;

    @SerializedName("target_content_type")
    private String targetContentType;

    @SerializedName("details")
    private String details;

    @SerializedName("ip_address")
    private String ipAddress;

    @SerializedName("user_agent")
    private String userAgent;

    @SerializedName("created_at")
    private String createdAt;

    // Геттеры и сеттеры
    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getAdminId() { return adminId; }
    public void setAdminId(int adminId) { this.adminId = adminId; }

    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }

    public Integer getTargetCompanyId() { return targetCompanyId; }
    public void setTargetCompanyId(Integer targetCompanyId) { this.targetCompanyId = targetCompanyId; }

    public Integer getTargetObjectId() { return targetObjectId; }
    public void setTargetObjectId(Integer targetObjectId) { this.targetObjectId = targetObjectId; }

    public String getTargetContentType() { return targetContentType; }
    public void setTargetContentType(String targetContentType) { this.targetContentType = targetContentType; }

    public String getDetails() { return details; }
    public void setDetails(String details) { this.details = details; }

    public String getIpAddress() { return ipAddress; }
    public void setIpAddress(String ipAddress) { this.ipAddress = ipAddress; }

    public String getUserAgent() { return userAgent; }
    public void setUserAgent(String userAgent) { this.userAgent = userAgent; }

    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
}