package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class FeedVideoItem {

    @SerializedName("id")
    private int id;

    @SerializedName("video")
    private String videoUrl;

    @SerializedName("description")
    private String description;

    // ВАЖНО: тут объект!
    @SerializedName("vacancy")
    private Vacancy vacancy;

    @SerializedName("likes_count")
    private int likesCount;

    @SerializedName("views_count")
    private int viewsCount;

    @SerializedName("is_liked")
    private boolean isLiked;

    @SerializedName("created_at")
    private String createdAt;


    public void setLiked(boolean liked) {
        isLiked = liked;
    }

    public void setLikesCount(int likesCount) {
        this.likesCount = likesCount;
    }

    public int getId() { return id; }
    public String getVideoUrl() { return videoUrl; }
    public String getDescription() { return description; }
    public Vacancy getVacancy() { return vacancy; }
    public int getLikesCount() { return likesCount; }
    public int getViewsCount() { return viewsCount; }
    public boolean isLiked() { return isLiked; }
    public String getCreatedAt() { return createdAt; }
}
