package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class VacancyDetails {
    @SerializedName("id")
    private int id;

    @SerializedName("position")
    private String position;

    @SerializedName("company_name")
    private String companyName;

    @SerializedName("city")
    private String city;

    @SerializedName("description")
    private String description;

    @SerializedName("salary")
    private String salary;

    @SerializedName("experience")
    private String experience;

    @SerializedName("category")
    private String category;

    @SerializedName("employment_type")
    private String employmentType;

    @SerializedName("work_schedule")
    private String workSchedule;

    @SerializedName("requirements")
    private String requirements;

    @SerializedName("responsibilities")
    private String responsibilities;

    @SerializedName("conditions")
    private String conditions;

    @SerializedName("skills")
    private String skills;

    @SerializedName("education")
    private String education;

    @SerializedName("views_count")
    private int viewsCount;

    @SerializedName("created_at")
    private String createdAt;

    @SerializedName("is_favorite")
    private boolean isFavorite;

    // Добавляем это поле для статуса отклика
    @SerializedName("has_applied")
    private boolean hasApplied;

    // Геттеры и сеттеры
    public int getId() {
        return id;
    }

    public String getPosition() {
        return position;
    }

    public String getCompanyName() {
        return companyName;
    }

    public String getCity() {
        return city;
    }

    public String getDescription() {
        return description;
    }

    public String getSalary() {
        return salary;
    }

    public String getExperience() {
        return experience;
    }

    public String getCategory() {
        return category;
    }

    public String getEmploymentType() {
        return employmentType;
    }

    public String getWorkSchedule() {
        return workSchedule;
    }

    public String getRequirements() {
        return requirements;
    }

    public String getResponsibilities() {
        return responsibilities;
    }

    public String getConditions() {
        return conditions;
    }

    public String getSkills() {
        return skills;
    }

    public String getEducation() {
        return education;
    }

    public int getViewsCount() {
        return viewsCount;
    }

    public String getCreatedAt() {
        return createdAt;
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

    public void setCity(String city) {
        this.city = city;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public void setSalary(String salary) {
        this.salary = salary;
    }

    public void setExperience(String experience) {
        this.experience = experience;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public void setEmploymentType(String employmentType) {
        this.employmentType = employmentType;
    }

    public void setWorkSchedule(String workSchedule) {
        this.workSchedule = workSchedule;
    }

    public void setRequirements(String requirements) {
        this.requirements = requirements;
    }

    public void setResponsibilities(String responsibilities) {
        this.responsibilities = responsibilities;
    }

    public void setConditions(String conditions) {
        this.conditions = conditions;
    }

    public void setSkills(String skills) {
        this.skills = skills;
    }

    public void setEducation(String education) {
        this.education = education;
    }

    public void setViewsCount(int viewsCount) {
        this.viewsCount = viewsCount;
    }

    public void setCreatedAt(String createdAt) {
        this.createdAt = createdAt;
    }

    public void setFavorite(boolean favorite) {
        isFavorite = favorite;
    }

    public void setHasApplied(boolean hasApplied) {
        this.hasApplied = hasApplied;
    }
}