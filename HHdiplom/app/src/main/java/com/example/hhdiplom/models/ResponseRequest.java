package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ResponseRequest {

    @SerializedName("vacancy")
    private int vacancyId;

    // Конструктор для создания отклика
    public ResponseRequest(int vacancyId) {
        this.vacancyId = vacancyId;
        // Не отправляем applicantId - сервер получит его из текущего пользователя
        // Не отправляем statusId - сервер установит статус по умолчанию
    }

    // Только геттеры/сеттеры для vacancyId
    public int getVacancyId() {
        return vacancyId;
    }

    public void setVacancyId(int vacancyId) {
        this.vacancyId = vacancyId;
    }
}