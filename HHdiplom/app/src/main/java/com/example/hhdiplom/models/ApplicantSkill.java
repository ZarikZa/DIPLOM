package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;
public class ApplicantSkill {

    @SerializedName("skill")
    public int skill;   // id навыка

    @SerializedName("skill_name")
    public String skillName;

    @SerializedName("level")
    public int level;
}
