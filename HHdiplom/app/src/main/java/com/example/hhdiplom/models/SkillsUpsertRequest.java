package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

import java.util.List;

public class SkillsUpsertRequest {
    @SerializedName("skills")
    public List<SkillLevel> skills;

    public SkillsUpsertRequest(List<SkillLevel> skills) {
        this.skills = skills;
    }

    public static class SkillLevel {
        @SerializedName("skill_id") public int skillId;
        @SerializedName("level") public int level;

        public SkillLevel(int skillId, int level) {
            this.skillId = skillId;
            this.level = level;
        }
    }
}
