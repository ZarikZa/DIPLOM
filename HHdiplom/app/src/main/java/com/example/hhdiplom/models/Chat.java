package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Chat {

    @SerializedName("id")
    private int id;

    @SerializedName("vacancy")
    private int vacancyId;

    @SerializedName("company_name")
    private String companyName;

    @SerializedName("vacancy_title")
    private String vacancyTitle;

    @SerializedName("last_message")
    private LastMessage lastMessage;

    @SerializedName("unread_count")
    private int unreadCount;

    public int getId() {
        return id;
    }

    public int getVacancyId() {
        return vacancyId;
    }

    public String getCompanyName() {
        return companyName;
    }

    public String getVacancyTitle() {
        return vacancyTitle;
    }

    public LastMessage getLastMessage() {
        return lastMessage;
    }

    public int getUnreadCount() {
        return unreadCount;
    }

    public static class LastMessage {
        @SerializedName("text")
        private String text;

        @SerializedName("created_at")
        private String createdAt;

        @SerializedName("sender_type")
        private String senderType;

        public String getText() {
            return text != null ? text : "";
        }

        public String getCreatedAt() {
            return createdAt != null ? createdAt : "";
        }

        public String getSenderType() {
            return senderType;
        }
    }
}
