// SendMessageRequest.java
package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class SendMessageRequest {
    @SerializedName("text")
    private String text;

    public SendMessageRequest(String text) {
        this.text = text;
    }

    public String getText() { return text; }
    public void setText(String text) { this.text = text; }
}