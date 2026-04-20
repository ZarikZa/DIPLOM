package com.example.hhdiplom.models;

public class ToggleFavoriteRequest {
    private int vacancy;

    public ToggleFavoriteRequest(int vacancy) {
        this.vacancy = vacancy;
    }

    public int getVacancy() {
        return vacancy;
    }
}
