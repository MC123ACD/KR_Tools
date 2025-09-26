local script_utils = {}

function script_utils.merge_conflict_tables(t1, t2)
    local merged = {}

    -- 遍历 t1 的所有键值对
    for key, value in pairs(t1) do
        merged[key] = value
    end

    -- 遍历 t2 的所有键值对，添加 t1 中没有的键
    for key, value in pairs(t2) do
        if not t1[key] then
            merged[key] = value
        end
    end

    return merged
end

---合并两个表（递归合并，数组去重合并）
---@param t1 table 表1
---@param t2 table 表2
---@return table 合并后的新表
function script_utils.merge_tables(t1, t2)
    local merged = {}

    -- 遍历 t1 的所有键值对
    for key, value in pairs(t1) do
        if t2[key] then
            -- 如果 t2 中也有相同的键，并且值是表
            if type(value) == "table" and type(t2[key]) == "table" then
                -- 如果是数组（所有键是连续的数字），合并数组
                if #value > 0 and #t2[key] > 0 then
                    local set = {}
                    for _, v in ipairs(value) do
                        set[v] = true
                    end
                    for _, v in ipairs(t2[key]) do
                        set[v] = true
                    end
                    merged[key] = {}
                    for v, _ in pairs(set) do
                        table.insert(merged[key], v)
                    end
                else
                    -- 否则递归合并
                    merged[key] = merge_tables(value, t2[key])
                end
            else
                -- 如果不是表，优先保留 t1 的值
                merged[key] = value
            end
        else
            -- 如果 t2 中没有这个键，直接保留 t1 的值
            merged[key] = value
        end
    end

    -- 遍历 t2 的所有键值对，添加 t1 中没有的键
    for key, value in pairs(t2) do
        if not t1[key] then
            merged[key] = value
        end
    end

    return merged
end

return script_utils