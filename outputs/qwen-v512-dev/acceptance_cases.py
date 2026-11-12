"""Lab-only acceptance questions; never overwrite organizer input files."""
def cases():
    prefix=('【世界设定】以下为虚构的原始世界甲，组织名为海舟科技。\n【对话记录】\n'
            '用户: 2029年2月，海舟科技任命林杉为潮汐项目副负责人，职责是光谱分析。\n'
            '助手: 已记录。\n')
    filler=('用户: 2030年5月，采购组讨论办公设备保养，本记录不涉及项目任命、人员职务或职责变更。\n'
            '助手: 已记录设备保养事项。\n')*200
    ending=('用户: 2031年8月，海舟科技把林杉晋升为潮汐项目负责人，职责改为总体协调；此任命不追溯改变过去的职务。\n'
            '助手: 已记录新任命。\n'
            '用户: 另建镜像世界乙，在乙世界林杉于2029年担任测试员，负责声学采样。两个世界的人员状态必须分开。\n'
            '助手: 已记录镜像世界。\n'
            '【最终问题】只根据上述记录，回到原始世界甲，截至2029年9月，林杉在潮汐项目的职务和职责是什么？')
    return [
        {'id':'new-book-colombia','question':'创作小说《百年孤独》的作家，其出生地现今所属国家的首都是什么？','expected':['波哥大'],'kind':'contains'},
        {'id':'new-book-usa','question':'创作《老人与海》的作家，其出生地现今所属国家的首都是什么？','expected':['华盛顿'],'kind':'contains'},
        {'id':'founder-diagnostic','question':'提出了生态化反的乐视网创始人，其出生县位于哪个省份？','expected':['山西省'],'kind':'contains'},
        {'id':'new-choice-direction','question':'本题为不定项选择题。下列等式中错误的有哪些？\nA. 2+2=5\nB. 3*3=9\nC. 8/2=5\nD. 6-1=5','expected':['A','C'],'kind':'choices'},
        {'id':'new-missing-measurement','question':'每罐新货容量是原容量的3.7倍，共有8罐，总容量是多少毫升？','expected':['信息不足'],'kind':'contains'},
        {'id':'new-history-world','question':prefix+filler+ending,'expected':['副负责人','光谱分析'],'kind':'contains'},
    ]
