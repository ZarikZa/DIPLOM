package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class VacancyVideo {

    @SerializedName("id")
    private int id;

    @SerializedName("video")
    private String videoUrl;

    @SerializedName("description")
    private String description;

    // сервер отдаёт ЧИСЛО
    @SerializedName("vacancy")
    private Integer vacancyId;

    // сервер может отдавать строку
    @SerializedName("vacancy_position")
    private String vacancyPosition;

    @SerializedName("likes_count")
    private int likesCount;

    @SerializedName("views_count")
    private int viewsCount;

    @SerializedName("is_liked")
    private boolean isLiked;

    public int getId() { return id; }
    public String getVideoUrl() { return videoUrl; }
    public String getDescription() { return description; }

    public Integer getVacancyId() { return vacancyId; }
    public String getVacancyPosition() { return vacancyPosition; }

    public int getLikes() { return likesCount; }
    public int getViews() { return viewsCount; }
    public boolean isLiked() { return isLiked; }

    public void setLikes(int likesCount) { this.likesCount = likesCount; }
    public void setViews(int viewsCount) { this.viewsCount = viewsCount; }
    public void setLiked(boolean liked) { isLiked = liked; }
}
