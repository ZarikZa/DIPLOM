package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Vacancy {
    @SerializedName("id")
    private int id;

    @SerializedName("position")
    private String position;

    @SerializedName("company_name")
    private String companyName;

    @SerializedName("salary_min")
    private String salaryMin;

    @SerializedName("salary_max")
    private String salaryMax;

    @SerializedName("city")
    private String city;

    @SerializedName("category")
    private String category;

    @SerializedName("experience")
    private String experience;

    @SerializedName("status_name")
    private String statusName;

    @SerializedName("views")
    private int views;

    @SerializedName("created_date")
    private String createdDate;

    @SerializedName("is_favorite")
    private boolean isFavorite;

    @SerializedName("has_applied")  // Это новое поле!
    private boolean hasApplied;

    @SerializedName("has_video")
    private boolean hasVideo;

    @SerializedName("video_id")
    private Integer videoId;

    public boolean hasVideo() { return hasVideo; }
    public Integer getVideoId() { return videoId; }


    public int getId() {
        return id;
    }

    public String getPosition() {
        return position;
    }

    public String getCompanyName() {
        return companyName;
    }

    public String getSalaryMin() {
        return salaryMin;
    }

    public String getSalaryMax() {
        return salaryMax;
    }

    public String getCity() {
        return city;
    }

    public String getCategory() {
        return category;
    }

    public String getExperience() {
        return experience;
    }

    public String getStatusName() {
        return statusName;
    }

    public int getViews() {
        return views;
    }

    public String getCreatedDate() {
        return createdDate;
    }

    public boolean isFavorite() {
        return isFavorite;
    }

    public boolean isHasApplied() {
        return hasApplied;
    }

    public void setId(int id) {
        this.id = id;
    }

    public void setPosition(String position) {
        this.position = position;
    }

    public void setCompanyName(String companyName) {
        this.companyName = companyName;
    }

    public void setSalaryMin(String salaryMin) {
        this.salaryMin = salaryMin;
    }

    public void setSalaryMax(String salaryMax) {
        this.salaryMax = salaryMax;
    }

    public void setCity(String city) {
        this.city = city;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public void setExperience(String experience) {
        this.experience = experience;
    }

    public void setStatusName(String statusName) {
        this.statusName = statusName;
    }

    public void setViews(int views) {
        this.views = views;
    }

    public void setCreatedDate(String createdDate) {
        this.createdDate = createdDate;
    }

    public void setFavorite(boolean favorite) {
        isFavorite = favorite;
    }

    public void setHasApplied(boolean hasApplied) {
        this.hasApplied = hasApplied;
    }
}