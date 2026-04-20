package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ApplicantSkillItem {
    @SerializedName("skill") public int skillId;
    @SerializedName("level") public int level;
    @SerializedName("skill_name") public String skillName;
}
