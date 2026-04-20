package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class VacancyVideoUploadResponse {

    @SerializedName("id")
    private int id;

    // сервер возвращает число
    @SerializedName("vacancy")
    private int vacancy;

    @SerializedName("video")
    private String videoUrl; // может быть null

    @SerializedName("description")
    private String description;

    @SerializedName("is_active")
    private Boolean isActive; // если отдаёшь

    public int getId() { return id; }
    public int getVacancy() { return vacancy; }
    public String getVideoUrl() { return videoUrl; }
    public String getDescription() { return description; }
    public Boolean getIsActive() { return isActive; }
}
