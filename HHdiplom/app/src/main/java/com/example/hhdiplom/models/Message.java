// Message.java
package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Message {
    @SerializedName("id")
    private int id;

    @SerializedName("text")
    private String text;

    @SerializedName("sender_email")
    private String senderEmail;

    @SerializedName("sender_name")
    private String senderName;

    @SerializedName("is_my_message")
    private boolean isMyMessage;

    @SerializedName("is_read")
    private boolean isRead;

    @SerializedName("created_at")
    private String createdAt;

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public String getText() { return text; }
    public void setText(String text) { this.text = text; }

    public String getSenderEmail() { return senderEmail; }
    public void setSenderEmail(String senderEmail) { this.senderEmail = senderEmail; }

    public String getSenderName() { return senderName; }
    public void setSenderName(String senderName) { this.senderName = senderName; }

    public boolean isMyMessage() { return isMyMessage; }
    public void setMyMessage(boolean myMessage) { isMyMessage = myMessage; }

    public boolean isRead() { return isRead; }
    public void setRead(boolean read) { isRead = read; }

    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
}