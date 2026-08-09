`timescale 1ns/1ps

module stream_bench (
    input  logic        clk,
    input  logic        reset_n,

    input  logic        s_valid,
    output logic        s_ready,
    input  logic [63:0] s_data,
    input  logic [15:0] s_id,
    input  logic        s_last,
    input  logic [7:0]  s_user,

    output logic        m_valid,
    input  logic        m_ready,
    output logic [63:0] m_data,
    output logic [15:0] m_id,
    output logic        m_last,
    output logic [7:0]  m_user,

    input  logic        inject_error,
    output logic [63:0] accepted_count
);
    logic [63:0] mixed_data;
    logic [63:0] transformed_data;

    always_comb begin
        s_ready = m_ready;
        m_valid = s_valid;
        mixed_data = s_data ^ 64'hd6e8_feb8_6659_fd93;
        transformed_data = {mixed_data[50:0], mixed_data[63:51]};
        transformed_data = transformed_data
            + 64'ha5a5_5a5a_1234_5678
            + {{48{1'b0}}, s_id};
        m_data = transformed_data;
        if (inject_error && (accepted_count == 64'd127)) begin
            m_data[0] = ~m_data[0];
        end
        m_id = s_id;
        m_last = s_last;
        m_user = s_user;
    end

    always_ff @(posedge clk) begin
        if (!reset_n) begin
            accepted_count <= 64'd0;
        end else if (s_valid && s_ready) begin
            accepted_count <= accepted_count + 64'd1;
        end
    end
endmodule
