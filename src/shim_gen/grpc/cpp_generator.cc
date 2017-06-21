/*
 *
 * Copyright 2015, Google Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 *     * Redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer.
 *     * Redistributions in binary form must reproduce the above
 * copyright notice, this list of conditions and the following disclaimer
 * in the documentation and/or other materials provided with the
 * distribution.
 *     * Neither the name of Google Inc. nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 */

#include <map>
#include <sstream>

#include "fmt/format.h"
#include "glog/logging.h"

#include "common/macros.h"
#include "common/string_util.h"
#include "shim_gen/grpc/cpp_generator.h"

namespace fluent_cpp_generator {

namespace {

std::string FilenameIdentifier(const std::string &filename) {
  std::string result;
  for (unsigned i = 0; i < filename.size(); i++) {
    char c = filename[i];
    if (isalnum(c)) {
      result.push_back(c);
    } else {
      static char hex[] = "0123456789abcdef";
      result.push_back('_');
      result.push_back(hex[(c >> 4) & 0xf]);
      result.push_back(hex[c & 0xf]);
    }
  }
  return result;
}

std::vector<std::string> FieldTypes(const google::protobuf::Descriptor &msg) {
  std::vector<std::string> field_types;
  for (int i = 0; i < msg.field_count(); ++i) {
    const google::protobuf::FieldDescriptor *field = msg.field(i);
    switch (field->cpp_type()) {
      case google::protobuf::FieldDescriptor::CPPTYPE_INT32:
      case google::protobuf::FieldDescriptor::CPPTYPE_INT64:
      case google::protobuf::FieldDescriptor::CPPTYPE_UINT32:
      case google::protobuf::FieldDescriptor::CPPTYPE_UINT64:
      case google::protobuf::FieldDescriptor::CPPTYPE_DOUBLE:
      case google::protobuf::FieldDescriptor::CPPTYPE_FLOAT:
      case google::protobuf::FieldDescriptor::CPPTYPE_BOOL: {
        field_types.push_back(field->cpp_type_name());
        break;
      }
      case google::protobuf::FieldDescriptor::CPPTYPE_STRING: {
        // cpp_type_name returns "string".
        field_types.push_back("std::string");
        break;
      }
      case google::protobuf::FieldDescriptor::CPPTYPE_ENUM: {
        break;
        field_types.push_back(DotsToColons(field->enum_type()->full_name()));
      }
      case google::protobuf::FieldDescriptor::CPPTYPE_MESSAGE: {
        field_types.push_back(DotsToColons(field->message_type()->full_name()));
        break;
      }
      default: {
        CHECK(false) << "Unreachable code.";
        break;
      }
    }
  }
  return field_types;
}

std::vector<std::string> FieldNames(const google::protobuf::Descriptor &msg) {
  std::vector<std::string> field_names;
  for (int i = 0; i < msg.field_count(); ++i) {
    const google::protobuf::FieldDescriptor *field = msg.field(i);
    field_names.push_back(field->name());
  }
  return field_names;
}

}  // namespace

std::string GetPrologue(ProtoBufFile *file, const Parameters &params) {
  UNUSED(params);

  std::string output;
  {
    // Scope the output stream so it closes and finalizes output to the string.
    auto printer = file->CreatePrinter(&output);
    std::map<std::string, std::string> vars;

    vars["filename"] = file->filename();
    vars["filename_identifier"] = FilenameIdentifier(file->filename());
    vars["filename_base"] = file->filename_without_ext();
    vars["message_header_ext"] = kCppGeneratorMessageHeaderExt;

    printer->Print(vars, "// Generated by the gRPC fluent plugin.\n");
    printer->Print(vars,
                   "// If you make any local change, they will be lost.\n");
    printer->Print(vars, "// source: $filename$\n");
    std::string leading_comments = file->GetLeadingComments("//");
    if (!leading_comments.empty()) {
      printer->Print(vars, "// Original file comments:\n");
      printer->Print(leading_comments.c_str());
    }
    printer->Print(vars, "#ifndef FLUENT_$filename_identifier$__INCLUDED\n");
    printer->Print(vars, "#define FLUENT_$filename_identifier$__INCLUDED\n");
    printer->Print(vars, "\n");
    printer->Print(vars, "#include \"$filename_base$$message_header_ext$\"\n");
    printer->Print(vars, file->additional_headers().c_str());
    printer->Print(vars, "\n");
  }
  return output;
}

std::string GetIncludes(ProtoBufFile *file, const Parameters &params) {
  UNUSED(params);

  std::string output;
  {
    // Scope the output stream so it closes and finalizes output to the string.
    auto printer = file->CreatePrinter(&output);
    std::map<std::string, std::string> vars;

    printer->Print(vars, "#include <cstdint>\n");
    printer->Print(vars, "\n");
    printer->Print(vars, "#include <string>\n");
    printer->Print(vars, "#include <tuple>\n");
    printer->Print(vars, "#include <utility>\n");
    printer->Print(vars, "\n");
    printer->Print(vars, "#include \"fluent/infix.h\"\n");
    printer->Print(vars, "#include \"grpc++/grpc++.h\"\n");
    printer->Print(vars, "\n");
    printer->Print(vars, "#include \"examples/grpc/api.grpc.pb.h\"\n");
    printer->Print(vars, "#include \"examples/grpc/api.pb.h\"\n");
    printer->Print(vars, "#include \"ra/logical/all.h\"\n");
    printer->Print(vars, "\n");

    if (!file->package().empty()) {
      std::vector<std::string> parts = file->package_parts();
      for (auto part = parts.begin(); part != parts.end(); part++) {
        vars["part"] = *part;
        printer->Print(vars, "namespace $part$ {\n");
      }
      printer->Print(vars, "\n");
    }
  }
  return output;
}

void PrintClientMethod(const fluent_generator::Method &method,
                       const Parameters &params,
                       fluent_generator::Printer *printer) {
  UNUSED(params);

  const google::protobuf::Descriptor *in_type = method.input_type();
  const std::vector<std::string> in_field_types = FieldTypes(*in_type);
  const std::vector<std::string> in_field_names = FieldNames(*in_type);

  const google::protobuf::Descriptor *out_type = method.output_type();
  const std::vector<std::string> out_field_types = FieldTypes(*out_type);
  const std::vector<std::string> out_field_names = FieldNames(*out_type);

  std::map<std::string, std::string> vars;
  vars["request_type"] = DotsToColons(in_type->full_name());
  vars["reply_type"] = DotsToColons(out_type->full_name());
  vars["method_name"] = method.name();

  // Method signature.
  vars["output_type"] =
      fmt::format("std::tuple<{}>", fluent::Join(out_field_types));
  printer->Print(vars, "$output_type$ ");
  printer->Print(vars, "$method_name$(");
  for (std::size_t j = 0; j < in_field_types.size(); ++j) {
    vars["input_type"] = in_field_types[j];
    vars["input_name"] = in_field_names[j];
    printer->Print(vars, "const $input_type$& $input_name$");
    if (j != in_field_types.size() - 1) {
      printer->Print(vars, ", ");
    }
  }
  printer->Print(vars, ") {\n");
  printer->Indent();

  // Request.
  printer->Print(vars, "// Request.\n");
  printer->Print(vars, "$request_type$ request;\n");
  for (std::size_t j = 0; j < in_field_types.size(); ++j) {
    const google::protobuf::FieldDescriptor *field = in_type->field(j);
    vars["input_type"] = in_field_types[j];
    vars["input_name"] = in_field_names[j];
    if (field->type() == google::protobuf::FieldDescriptor::TYPE_MESSAGE) {
      printer->Print(vars, "*request.mutable_$input_name$() = $input_name$;\n");
    } else {
      printer->Print(vars, "request.set_$input_name$($input_name$);\n");
    }
  }
  printer->Print(vars, "\n");

  // Reply.
  printer->Print(vars, "// Reply.\n");
  printer->Print(vars, "$reply_type$ reply;\n\n");

  // RPC call.
  printer->Print(vars, "// RPC call.\n");
  printer->Print(vars, "grpc::ClientContext context;\n");
  printer->Print(vars,
                 "grpc::Status status = stub_->$method_name$("
                 "&context, request, &reply);\n");
  printer->Print(vars, "CHECK(status.ok());\n\n");

  // Return.
  printer->Print(vars, "return $output_type$(");
  for (std::size_t j = 0; j < out_field_types.size(); ++j) {
    vars["output_name"] = out_field_names[j];
    printer->Print(vars, "reply.$output_name$()");
    if (j != in_field_types.size() - 1) {
      printer->Print(vars, ", ");
    }
  }
  printer->Print(vars, ");\n");

  // Method end.
  printer->Outdent();
  printer->Print(vars, "}\n\n");
}

std::string GetClientClass(ProtoBufFile *file, const Parameters &params) {
  UNUSED(params);
  CHECK_EQ(file->service_count(), 1);
  std::unique_ptr<const fluent_generator::Service> service = file->service(0);

  std::string output;
  {
    auto printer = file->CreatePrinter(&output);
    std::map<std::string, std::string> vars;
    vars["Service"] = service->name();

    // Class.
    printer->Print(service->GetLeadingComments("//").c_str());
    printer->Print(vars, "class $Service$Client final {\n");
    printer->Print(vars, " public:\n");
    printer->Indent();

    // Constructor.
    printer->Print(vars,
                   "$Service$Client(std::shared_ptr<grpc::Channel> channel)");
    printer->Print(vars, " : stub_($Service$::NewStub(channel)) {}");
    printer->Print(vars, "\n\n");

    // Methods.
    for (int i = 0; i < service->method_count(); ++i) {
      std::unique_ptr<const fluent_generator::Method> method =
          service->method(i);
      PrintClientMethod(*method, params, printer.get());
    }

    // Private members.
    printer->Outdent();
    printer->Print(vars, " private:\n");
    printer->Print(vars, "  std::unique_ptr<$Service$::Stub> stub_;\n");
    printer->Print(vars, "};\n\n");
  }
  return output;
}

void PrintMethodCollections(const fluent_generator::Method &method,
                            const Parameters &params,
                            fluent_generator::Printer *printer) {
  UNUSED(params);

  const google::protobuf::Descriptor *in_type = method.input_type();
  const std::vector<std::string> in_field_types = FieldTypes(*in_type);
  const std::vector<std::string> in_field_names = FieldNames(*in_type);

  const google::protobuf::Descriptor *out_type = method.output_type();
  const std::vector<std::string> out_field_types = FieldTypes(*out_type);
  const std::vector<std::string> out_field_names = FieldNames(*out_type);

  std::map<std::string, std::string> vars;
  vars["request_types"] = fluent::Join(in_field_types);
  vars["reply_types"] = fluent::Join(out_field_types);
  vars["method_name"] = method.name();

  // Request channel.
  printer->Print(vars,
                 ".template channel<"
                 "std::string, std::string, std::int64_t, $request_types$"
                 ">(\"$method_name$_request\", "
                 "{{\"dst_addr\", \"src_addr\", \"id\", ");
  for (std::size_t i = 0; i < in_field_names.size(); ++i) {
    vars["column_name"] = in_field_names[i];
    printer->Print(vars, "\"$column_name$\"");
    if (i != in_field_names.size() - 1) {
      printer->Print(vars, ", ");
    }
  }
  printer->Print(vars, "}})\n");

  // Reply channel.
  printer->Print(vars,
                 ".template channel<std::string, std::int64_t, $reply_types$>"
                 "(\"$method_name$_reply\", "
                 "{{\"addr\", \"id\", ");
  for (std::size_t i = 0; i < out_field_names.size(); ++i) {
    vars["column_name"] = out_field_names[i];
    printer->Print(vars, "\"$column_name$\"");
    if (i != out_field_names.size() - 1) {
      printer->Print(vars, ", ");
    }
  }
  printer->Print(vars, "}})\n");
}

std::string GetApiFunction(ProtoBufFile *file, const Parameters &params) {
  UNUSED(params);
  CHECK_EQ(file->service_count(), 1);
  std::unique_ptr<const fluent_generator::Service> service = file->service(0);

  std::string output;
  {
    auto printer = file->CreatePrinter(&output);
    std::map<std::string, std::string> vars;
    vars["Service"] = service->name();

    // Method signature.
    printer->Print(vars, "template <typename FluentBuilder>\n");
    printer->Print(vars, "auto Add$Service$Api(FluentBuilder f) {\n");
    printer->Indent();

    // Method body.
    printer->Print(vars, "return std::move(f)\n");
    printer->Indent();
    for (int i = 0; i < service->method_count(); ++i) {
      std::unique_ptr<const fluent_generator::Method> method =
          service->method(i);
      PrintMethodCollections(*method, params, printer.get());
    }
    printer->Outdent();
    printer->Print(vars, ";\n");

    // Method end.
    printer->Outdent();
    printer->Print(vars, "}\n\n");
  }
  return output;
}

void PrintMethodRule(const fluent_generator::Method &method,
                     const Parameters &params,
                     fluent_generator::Printer *printer) {
  UNUSED(params);

  const google::protobuf::Descriptor *in_type = method.input_type();
  const std::vector<std::string> in_field_names = FieldNames(*in_type);

  std::map<std::string, std::string> vars;
  vars["method_name"] = method.name();

  // Rule head.
  printer->Print(vars, "auto $method_name$ = $method_name$_reply <= (\n");
  printer->Indent();
  printer->Print(
      vars, "fluent::ra::logical::make_collection(&$method_name$_request) |\n");
  printer->Print(vars, "fluent::ra::logical::map([client](const auto& t) {\n");
  printer->Indent();

  // Rule body.
  printer->Print(vars, "const std::string& src_addr = std::get<1>(t);\n");
  printer->Print(vars, "const std::int64_t id = std::get<2>(t);\n");
  printer->Print(vars,
                 "return std::tuple_cat(std::make_tuple(src_addr, id), "
                 "client->$method_name$(");
  for (std::size_t i = 0; i < in_field_names.size(); ++i) {
    printer->Print(vars,
                   ("std::get<" + std::to_string(i + 3) + ">(t)").c_str());
    if (i != in_field_names.size() - 1) {
      printer->Print(vars, ", ");
    }
  }
  printer->Print(vars, "));\n");

  // Rule tail.
  printer->Outdent();
  printer->Print(vars, "})\n");
  printer->Outdent();
  printer->Print(vars, ");\n\n");
}

std::string GetFluentFunction(ProtoBufFile *file, const Parameters &params) {
  UNUSED(params);
  CHECK_EQ(file->service_count(), 1);
  std::unique_ptr<const fluent_generator::Service> service = file->service(0);

  std::string output;
  {
    auto printer = file->CreatePrinter(&output);
    std::map<std::string, std::string> vars;
    vars["Service"] = service->name();

    // Method signature.
    printer->Print(vars, "template <typename FluentBuilder>\n");
    printer->Print(vars,
                   "auto Get$Service$Shim("
                   "FluentBuilder f, $Service$Client* client) {\n");
    printer->Indent();

    // RegisterRules head.
    printer->Print(vars, "return Add$Service$Api(std::move(f))\n");
    printer->Indent();
    printer->Print(vars, ".RegisterRules([client](");
    for (int i = 0; i < service->method_count(); ++i) {
      vars["method_name"] = service->method(i)->name();
      printer->Print(vars, "auto& $method_name$_request, ");
      printer->Print(vars, "auto& $method_name$_reply");
      if (i != service->method_count() - 1) {
        printer->Print(vars, ", ");
      }
    }
    printer->Print(vars, ") {\n");
    printer->Indent();
    printer->Print(vars, "using namespace fluent::infix;\n\n");

    // RegisterRules body.
    for (int i = 0; i < service->method_count(); ++i) {
      std::unique_ptr<const fluent_generator::Method> method =
          service->method(i);
      PrintMethodRule(*method, params, printer.get());
    }

    // RegisterRules return.
    printer->Print(vars, "return std::make_tuple(");
    for (int i = 0; i < service->method_count(); ++i) {
      vars["method_name"] = service->method(i)->name();
      printer->Print(vars, "$method_name$");
      if (i != service->method_count() - 1) {
        printer->Print(vars, ", ");
      }
    }
    printer->Print(vars, ");\n");
    printer->Outdent();
    printer->Print(vars, "});\n");
    printer->Outdent();

    // Method end.
    printer->Outdent();
    printer->Print(vars, "}\n\n");
  }
  return output;
}

std::string GetEpilogue(ProtoBufFile *file, const Parameters &params) {
  UNUSED(params);

  std::string output;
  {
    // Scope the output stream so it closes and finalizes output to the string.
    auto printer = file->CreatePrinter(&output);
    std::map<std::string, std::string> vars;

    vars["filename"] = file->filename();
    vars["filename_identifier"] = FilenameIdentifier(file->filename());

    if (!file->package().empty()) {
      std::vector<std::string> parts = file->package_parts();

      for (auto part = parts.rbegin(); part != parts.rend(); part++) {
        vars["part"] = *part;
        printer->Print(vars, "}  // namespace $part$\n");
      }
      printer->Print(vars, "\n");
    }

    printer->Print(vars, "\n");
    printer->Print(vars, "#endif  // GRPC_$filename_identifier$__INCLUDED\n");

    printer->Print(file->GetTrailingComments("//").c_str());
  }
  return output;
}

}  // namespace fluent_cpp_generator
