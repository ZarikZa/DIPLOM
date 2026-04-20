package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class CmVideoItem {

    @SerializedName("id")
    private int id;

    @SerializedName("video")
    private String videoUrl;

    @SerializedName("description")
    private String description;

    @SerializedName("vacancy")
    private int vacancyId;

    @SerializedName("vacancy_position")
    private String vacancyPosition;

    @SerializedName("likes_count")
    private int likesCount;

    @SerializedName("views_count")
    private int viewsCount;

    @SerializedName("is_active")
    private boolean isActive;

    public int getId() { return id; }
    public String getVideoUrl() { return videoUrl; }
    public String getDescription() { return description; }
    public int getVacancyId() { return vacancyId; }
    public String getVacancyPosition() { return vacancyPosition; }
    public int getLikesCount() { return likesCount; }
    public int getViewsCount() { return viewsCount; }
    public boolean isActive() { return isActive; }
}
