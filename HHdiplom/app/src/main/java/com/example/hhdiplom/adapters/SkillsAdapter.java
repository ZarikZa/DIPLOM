package com.example.hhdiplom.adapters;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.SeekBar;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.models.Skill;

import java.util.List;
import java.util.Map;

public class SkillsAdapter extends RecyclerView.Adapter<SkillsAdapter.VH> {

    private List<Skill> items;
    private final Map<Integer, Integer> levels; // skillId -> level

    public SkillsAdapter(List<Skill> items, Map<Integer, Integer> levels) {
        this.items = items;
        this.levels = levels;
    }

    public void setItems(List<Skill> newItems) {
        this.items = newItems;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_skill_level, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH holder, int position) {
        Skill s = items.get(position);
        holder.tvName.setText(s.getName());

        int cur = levels.containsKey(s.getId()) ? levels.get(s.getId()) : 0;
        holder.seek.setMax(5);
        holder.seek.setProgress(cur);
        holder.tvLevel.setText(cur + "/5");

        holder.seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                int val = Math.max(0, Math.min(5, progress));
                levels.put(s.getId(), val);
                holder.tvLevel.setText(val + "/5");
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });
    }

    @Override
    public int getItemCount() {
        return items == null ? 0 : items.size();
    }

    static class VH extends RecyclerView.ViewHolder {
        TextView tvName;
        TextView tvLevel;
        SeekBar seek;

        VH(@NonNull View itemView) {
            super(itemView);
            tvName = itemView.findViewById(R.id.tvSkillName);
            tvLevel = itemView.findViewById(R.id.tvSkillLevel);
            seek = itemView.findViewById(R.id.seekSkill);
        }
    }
}
