package com.example.hhdiplom.adapters;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.models.SkillItem;

import java.util.List;

public class SkillsSelectAdapter extends RecyclerView.Adapter<SkillsSelectAdapter.VH> {

    public static class SkillRow {
        public SkillItem skill;
        public boolean selected = false;
        public int level = 1; // 1..5
    }

    private final List<SkillRow> rows;

    public SkillsSelectAdapter(List<SkillRow> rows) {
        this.rows = rows;
    }

    public List<SkillRow> getRows() { return rows; }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_skill_select, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH h, int position) {
        SkillRow row = rows.get(position);

        h.tvSkillName.setText(row.skill.name);

        h.swSelected.setOnCheckedChangeListener(null);
        h.seekLevel.setOnSeekBarChangeListener(null);

        h.swSelected.setChecked(row.selected);
        h.levelContainer.setVisibility(row.selected ? View.VISIBLE : View.GONE);

        // выставляем уровень
        int progress = row.level - 1; // 0..4
        if (progress < 0) progress = 0;
        if (progress > 4) progress = 4;

        h.seekLevel.setProgress(progress);
        h.tvLevelValue.setText(String.valueOf(row.level));

        h.swSelected.setOnCheckedChangeListener((buttonView, isChecked) -> {
            row.selected = isChecked;
            h.levelContainer.setVisibility(isChecked ? View.VISIBLE : View.GONE);

            if (isChecked && row.level < 1) row.level = 1;
            h.tvLevelValue.setText(String.valueOf(row.level));
        });

        h.seekLevel.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar seekBar, int p, boolean fromUser) {
                row.level = p + 1; // 1..5
                h.tvLevelValue.setText(String.valueOf(row.level));
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });
    }

    @Override
    public int getItemCount() {
        return rows.size();
    }

    static class VH extends RecyclerView.ViewHolder {
        TextView tvSkillName, tvLevelValue;
        Switch swSelected;
        LinearLayout levelContainer;
        SeekBar seekLevel;

        VH(@NonNull View itemView) {
            super(itemView);
            tvSkillName = itemView.findViewById(R.id.tvSkillName);
            swSelected = itemView.findViewById(R.id.swSelected);
            levelContainer = itemView.findViewById(R.id.levelContainer);
            seekLevel = itemView.findViewById(R.id.seekLevel);
            tvLevelValue = itemView.findViewById(R.id.tvLevelValue);
        }
    }
}
