package com.example.hhdiplom.fragments;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.activities.ResponseDetailsActivity;
import com.example.hhdiplom.adapters.ResponsesAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.ResponseItem;
import com.example.hhdiplom.models.ResponsesResponse;
import com.google.android.material.chip.ChipGroup;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Locale;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ResponsesFragment extends Fragment {

    private static final int SEARCH_DELAY_MS = 300;

    private static final String FILTER_ALL = "all";
    private static final String FILTER_SENT = "sent";
    private static final String FILTER_PROGRESS = "progress";
    private static final String FILTER_INVITATION = "invitation";
    private static final String FILTER_REJECTED = "rejected";

    private static final String SORT_NEWEST = "newest";
    private static final String SORT_OLDEST = "oldest";
    private static final String SORT_STATUS = "status";

    private RecyclerView responsesRecyclerView;
    private ProgressBar progressBar;
    private LinearLayout emptyState;
    private EditText responseSearchEditText;
    private Spinner spinnerResponsesSort;
    private ChipGroup chipGroupResponseStatus;
    private TextView tvResponsesCount;

    private ResponsesAdapter adapter;
    private ApiService apiService;

    private final List<ResponseItem> allResponses = new ArrayList<>();

    private String selectedFilter = FILTER_ALL;
    private String selectedSort = SORT_NEWEST;

    private final Handler searchHandler = new Handler(Looper.getMainLooper());
    private Runnable searchRunnable;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_responses, container, false);

        ApiClient.init(requireContext());
        apiService = ApiClient.getApiService();

        initViews(view);
        setupSearch();
        setupSort();
        setupStatusFilter();
        loadResponses();

        return view;
    }

    private void initViews(View view) {
        responsesRecyclerView = view.findViewById(R.id.responsesRecyclerView);
        progressBar = view.findViewById(R.id.progressBar);
        emptyState = view.findViewById(R.id.emptyState);
        responseSearchEditText = view.findViewById(R.id.responseSearchEditText);
        spinnerResponsesSort = view.findViewById(R.id.spinnerResponsesSort);
        chipGroupResponseStatus = view.findViewById(R.id.chipGroupResponseStatus);
        tvResponsesCount = view.findViewById(R.id.tvResponsesCount);

        adapter = new ResponsesAdapter(new ArrayList<>(), this::showResponseDetails);

        responsesRecyclerView.setLayoutManager(new LinearLayoutManager(getContext()));
        responsesRecyclerView.setAdapter(adapter);

        updateCount(0);
    }

    private void setupSearch() {
        responseSearchEditText.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
            }

            @Override
            public void afterTextChanged(Editable s) {
                if (searchRunnable != null) {
                    searchHandler.removeCallbacks(searchRunnable);
                }
                searchRunnable = ResponsesFragment.this::applyClientFiltersAndSort;
                searchHandler.postDelayed(searchRunnable, SEARCH_DELAY_MS);
            }
        });
    }

    private void setupSort() {
        if (getContext() == null) {
            return;
        }

        List<String> sortTitles = Arrays.asList(
                getString(R.string.responses_sort_newest),
                getString(R.string.responses_sort_oldest),
                getString(R.string.responses_sort_status)
        );

        ArrayAdapter<String> sortAdapter = new ArrayAdapter<>(
                requireContext(),
                android.R.layout.simple_spinner_item,
                sortTitles
        );
        sortAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);

        spinnerResponsesSort.setAdapter(sortAdapter);
        spinnerResponsesSort.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                switch (position) {
                    case 1:
                        selectedSort = SORT_OLDEST;
                        break;
                    case 2:
                        selectedSort = SORT_STATUS;
                        break;
                    case 0:
                    default:
                        selectedSort = SORT_NEWEST;
                        break;
                }
                applyClientFiltersAndSort();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
    }

    private void setupStatusFilter() {
        chipGroupResponseStatus.setOnCheckedChangeListener((group, checkedId) -> {
            if (checkedId == R.id.chipResponseSent) {
                selectedFilter = FILTER_SENT;
            } else if (checkedId == R.id.chipResponseProgress) {
                selectedFilter = FILTER_PROGRESS;
            } else if (checkedId == R.id.chipResponseInvite) {
                selectedFilter = FILTER_INVITATION;
            } else if (checkedId == R.id.chipResponseRejected) {
                selectedFilter = FILTER_REJECTED;
            } else {
                selectedFilter = FILTER_ALL;
            }
            applyClientFiltersAndSort();
        });
    }

    private void loadResponses() {
        progressBar.setVisibility(View.VISIBLE);
        emptyState.setVisibility(View.GONE);

        Call<ResponsesResponse> call = apiService.getResponses();
        call.enqueue(new Callback<ResponsesResponse>() {
            @Override
            public void onResponse(Call<ResponsesResponse> call, Response<ResponsesResponse> response) {
                progressBar.setVisibility(View.GONE);

                if (response.isSuccessful() && response.body() != null) {
                    allResponses.clear();
                    if (response.body().getResults() != null) {
                        allResponses.addAll(response.body().getResults());
                    }
                    applyClientFiltersAndSort();
                } else {
                    handleError(response.code());
                }
            }

            @Override
            public void onFailure(Call<ResponsesResponse> call, Throwable t) {
                progressBar.setVisibility(View.GONE);
                allResponses.clear();
                adapter.updateList(new ArrayList<>());
                updateEmptyState();
                updateCount(0);

                if (getContext() != null) {
                    Toast.makeText(
                            getContext(),
                            getString(R.string.responses_error_network, t.getMessage()),
                            Toast.LENGTH_SHORT
                    ).show();
                }
            }
        });
    }

    private void applyClientFiltersAndSort() {
        String query = responseSearchEditText.getText().toString().trim().toLowerCase(Locale.getDefault());

        List<ResponseItem> filtered = new ArrayList<>();
        for (ResponseItem item : allResponses) {
            if (!matchesSearch(item, query)) {
                continue;
            }
            if (!matchesStatusFilter(item)) {
                continue;
            }
            filtered.add(item);
        }

        sortResponses(filtered);
        adapter.updateList(filtered);
        updateCount(filtered.size());
        updateEmptyState();
    }

    private boolean matchesSearch(ResponseItem item, String query) {
        if (query == null || query.isEmpty()) {
            return true;
        }

        return contains(item.getVacancyPosition(), query)
                || contains(item.getCompanyName(), query)
                || contains(item.getStatusName(), query);
    }

    private boolean contains(String source, String query) {
        if (source == null) {
            return false;
        }
        return source.toLowerCase(Locale.getDefault()).contains(query);
    }

    private boolean matchesStatusFilter(ResponseItem item) {
        if (FILTER_ALL.equals(selectedFilter)) {
            return true;
        }
        return selectedFilter.equals(classifyStatus(item));
    }

    private String classifyStatus(ResponseItem item) {
        String statusName = item.getStatusName() == null ? "" : item.getStatusName().toLowerCase(Locale.getDefault());

        if (statusName.contains("invite")
                || statusName.contains("priglash")
                || statusName.contains("\u043f\u0440\u0438\u0433\u043b\u0430\u0448")) {
            return FILTER_INVITATION;
        }
        if (statusName.contains("reject")
                || statusName.contains("otkaz")
                || statusName.contains("\u043e\u0442\u043a\u0430\u0437")) {
            return FILTER_REJECTED;
        }
        if (statusName.contains("progress")
                || statusName.contains("review")
                || statusName.contains("interview")
                || statusName.contains("process")
                || statusName.contains("\u043f\u0440\u043e\u0446\u0435\u0441\u0441")
                || statusName.contains("\u0440\u0430\u0441\u0441\u043c\u043e\u0442\u0440")
                || statusName.contains("\u0438\u043d\u0442\u0435\u0440\u0432\u044c\u044e")) {
            return FILTER_PROGRESS;
        }
        return FILTER_SENT;
    }

    private void sortResponses(List<ResponseItem> list) {
        Comparator<ResponseItem> comparator;
        switch (selectedSort) {
            case SORT_OLDEST:
                comparator = Comparator.comparingLong(item -> parseDate(item.getResponseDate()));
                break;
            case SORT_STATUS:
                comparator = (left, right) -> safeValue(left.getStatusName()).compareToIgnoreCase(safeValue(right.getStatusName()));
                break;
            case SORT_NEWEST:
            default:
                comparator = (left, right) -> Long.compare(parseDate(right.getResponseDate()), parseDate(left.getResponseDate()));
                break;
        }
        Collections.sort(list, comparator);
    }

    private long parseDate(String dateText) {
        if (dateText == null || dateText.trim().isEmpty()) {
            return 0L;
        }

        List<String> patterns = Arrays.asList(
                "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
                "yyyy-MM-dd'T'HH:mm:ssXXX",
                "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
                "yyyy-MM-dd'T'HH:mm:ss'Z'",
                "yyyy-MM-dd'T'HH:mm:ss"
        );

        for (String pattern : patterns) {
            try {
                SimpleDateFormat parser = new SimpleDateFormat(pattern, Locale.US);
                Date parsed = parser.parse(dateText);
                if (parsed != null) {
                    return parsed.getTime();
                }
            } catch (ParseException ignored) {
            }
        }

        return 0L;
    }

    private String safeValue(String value) {
        return value == null ? "" : value;
    }

    private void updateCount(int size) {
        tvResponsesCount.setText(getString(R.string.responses_count, size));
    }

    private void updateEmptyState() {
        if (adapter.getItemCount() == 0) {
            emptyState.setVisibility(View.VISIBLE);
            responsesRecyclerView.setVisibility(View.GONE);
        } else {
            emptyState.setVisibility(View.GONE);
            responsesRecyclerView.setVisibility(View.VISIBLE);
        }
    }

    private void handleError(int errorCode) {
        allResponses.clear();
        adapter.updateList(new ArrayList<>());
        updateEmptyState();
        updateCount(0);

        if (getContext() == null) {
            return;
        }

        switch (errorCode) {
            case 401:
                Toast.makeText(getContext(), getString(R.string.responses_error_auth), Toast.LENGTH_SHORT).show();
                break;
            case 404:
                Toast.makeText(getContext(), getString(R.string.responses_error_not_found), Toast.LENGTH_SHORT).show();
                break;
            default:
                Toast.makeText(getContext(), getString(R.string.error_with_code, errorCode), Toast.LENGTH_SHORT).show();
                break;
        }
    }

    private void showResponseDetails(ResponseItem response) {
        if (getContext() == null) {
            return;
        }
        Intent intent = ResponseDetailsActivity.createIntent(requireContext(), response);
        startActivity(intent);
    }

    public void refreshResponses() {
        loadResponses();
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        if (searchRunnable != null) {
            searchHandler.removeCallbacks(searchRunnable);
        }
    }
}
